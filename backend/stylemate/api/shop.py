"""Public routes used by the storefront and the chat widget."""

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from ..clients import ReferenceImage
from ..services import accounts, catalog, help, limits, orders, payments, pricing, sizes, uploads
from .helpers import current_customer, current_tenant, error, json_body, sender_key, services

bp = Blueprint("shop", __name__, url_prefix="/api")

VISITOR_ID_MAX = 64


@bp.get("/shop")
def shop_info():
    tenant = current_tenant()
    products = catalog.list_products(tenant)
    return jsonify({
        "name": tenant.name,
        "tagline": tenant.tagline,
        "shipping": pricing.shipping_options(tenant),
        "payment": payments.payment_options(tenant),
        "categories": sorted({product.category for product in products}),
        "occasions": sorted({occasion for product in products for occasion in product.to_dict()["occasions"]}),
    })


@bp.get("/products")
def product_list():
    return jsonify([product.to_dict() for product in catalog.list_products(current_tenant())])


@bp.get("/products/<code>")
def product_detail(code: str):
    tenant = current_tenant()
    product = catalog.get_product(tenant, code)
    data = product.to_dict()
    data["customization"] = pricing.options_for(tenant, product) if product.customizable else []
    data["custom_base_days"] = tenant.custom_base_days
    data["preview_available"] = bool(tenant.maira_image_profile_id)
    return jsonify(data)


@bp.post("/products/<code>/preview")
def product_preview(code: str):
    """A generated picture of the dress with the chosen changes, optionally on the customer."""
    tenant = current_tenant()
    photo = request.files.get("photo")
    limit = current_app.config["PREVIEWS_PER_DAY"]
    preview = services().preview.create(
        tenant,
        catalog.get_product(tenant, code),
        # Called by the service after its checks pass and just before the paid call
        before_drawing=lambda: limits.use(tenant, "preview", sender_key(), limit,
                                          "You've reached today's limit for picture previews. Please try again tomorrow."),
        visitor_id=_visitor_id(request.form.get("visitor_id")),
        colour=request.form.get("colour") or "",
        option_ids=request.form.getlist("option_ids"),
        wish=request.form.get("wish") or "",
        size=request.form.get("size") or "",
        measurements={name: request.form.get(name) for name in ("bust", "waist", "hip", "length")},
        photo=ReferenceImage(photo.filename or "photo", photo.read(), photo.mimetype or "") if photo else None,
    )
    return jsonify(preview.to_dict())


@bp.get("/size-guide")
def size_guide():
    return jsonify(sizes.size_guide(current_tenant()))


@bp.get("/help")
def help_page():
    return jsonify(help.help_page(current_tenant()))


@bp.post("/contact")
def contact():
    """A message to the owner, with an optional photo (sent as a form when there is one)."""
    body = request.form if request.form else json_body()
    tenant = current_tenant()
    photo = request.files.get("picture")
    content = photo.read() if photo else b""
    # Check everything first, so a mistyped form or a wrong file doesn't use up one of the day's messages
    message = help.check_message(body.get("name"), body.get("contact"), body.get("message"))
    if photo:
        uploads.check_picture(photo.mimetype or "", content)
    limits.use(tenant, "contact", sender_key(), current_app.config["CONTACT_MESSAGES_PER_DAY"],
               "You've sent several messages today. Please call or email us instead.")
    picture = uploads.save_picture(current_app.config["UPLOADS_DIR"], photo.mimetype, content) if photo else ""
    help.save_message(tenant, *message, picture=picture)
    return jsonify({"ok": True}), 201


@bp.post("/price-quote")
def price_quote():
    body = json_body()
    tenant = current_tenant()
    product = catalog.get_product(tenant, str(body.get("product_code") or ""))
    return jsonify(pricing.quote_for(tenant, product, body.get("option_ids") or []).to_dict())


@bp.post("/chat")
def chat():
    body = json_body()
    reply = services().chat.reply(
        current_tenant(),
        visitor_id=_visitor_id(body.get("visitor_id")),
        question=str(body.get("message") or ""),
        session_id=body.get("session_id") or None,
    )
    return jsonify(reply.to_dict())


@bp.post("/voice")
def voice():
    """Audio in, transcript plus the assistant's answer out."""
    audio = request.files.get("audio")
    if audio is None:
        return error("No recording received.", 400)

    transcript = services().chorus.transcribe(audio.read(), filename=audio.filename or "question.wav",
                                              mimetype=audio.mimetype or "audio/wav")
    if not transcript:
        return jsonify({"heard": False, "transcript": "",
                        "message": "Sorry, I didn't catch that. Could you try again?"})

    reply = services().chat.reply(
        current_tenant(),
        visitor_id=_visitor_id(request.form.get("visitor_id")),
        question=transcript,
        session_id=request.form.get("session_id") or None,
        via_voice=True,
    )
    return jsonify({"heard": True, "transcript": transcript, **reply.to_dict()})


@bp.post("/reference-pictures")
def upload_reference_picture():
    """A customer's picture for the tailor. Returns the name to send with the order."""
    picture = request.files.get("picture")
    if picture is None:
        return error("Choose a picture to upload.", 400)
    content = picture.read()
    uploads.check_picture(picture.mimetype or "", content)  # before counting, so a wrong file isn't counted
    limits.use(current_tenant(), "reference_picture", sender_key(), current_app.config["REFERENCE_PICTURES_PER_DAY"],
               "You've uploaded many pictures today. Please describe it in your notes instead.")
    name = uploads.save_picture(current_app.config["UPLOADS_DIR"], picture.mimetype, content)
    return jsonify({"reference_image": name}), 201


@bp.post("/orders")
def create_order():
    body = json_body()
    order = orders.place_order(current_tenant(), body.get("customer"), body.get("items") or [],
                               account=current_customer(), uploads_dir=current_app.config["UPLOADS_DIR"],
                               payment=body.get("payment"))
    return jsonify({**order.to_dict(), "customer_order_number": accounts.order_number(order)}), 201


@bp.get("/images/<path:filename>")
def product_image(filename: str):
    return send_from_directory(current_app.config["IMAGES_DIR"], filename, max_age=60)


def _visitor_id(value) -> str:
    value = str(value or "").strip()
    return value[:VISITOR_ID_MAX] or "guest"
