"""Product reviews. Only a customer who ordered the piece can review it, once."""

from ..errors import UserInputError
from ..extensions import db
from ..models import Customer, Order, OrderItem, Product, Review

MAX_COMMENT_LENGTH = 1000


def has_ordered(customer: Customer, product: Product) -> bool:
    return db.session.scalar(
        db.select(OrderItem.id).join(Order)
        .where(Order.customer_id == customer.id, OrderItem.product_id == product.id).limit(1)
    ) is not None


def product_reviews(product: Product, customer: Customer | None = None) -> dict:
    """Everything the product page needs: the reviews, the average, and whether this visitor may write one."""
    reviews = db.session.scalars(
        db.select(Review).where(Review.product_id == product.id).order_by(Review.created_at.desc(), Review.id.desc())
    ).all()
    mine = next((review for review in reviews if customer and review.customer_id == customer.id), None)
    if customer is None:
        blocked = "login"
    elif not has_ordered(customer, product):
        blocked = "not_ordered"
    else:
        blocked = ""
    return {
        "count": len(reviews),
        "average": round(sum(review.rating for review in reviews) / len(reviews), 1) if reviews else None,
        "reviews": [_public(review) for review in reviews],
        "can_review": not blocked,
        "blocked_reason": blocked,  # "login", "not_ordered" or ""
        "my_review": {"rating": mine.rating, "comment": mine.comment} if mine else None,
    }


def save_review(customer: Customer, product: Product, rating, comment) -> Review:
    """Add the customer's review, or replace the one they already wrote for this product."""
    if not has_ordered(customer, product):
        raise UserInputError("You can review a piece after you've ordered it.")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        raise UserInputError("Please choose a rating from 1 to 5 stars.")
    comment = str(comment or "").strip()
    if len(comment) > MAX_COMMENT_LENGTH:
        raise UserInputError(f"Please keep your review under {MAX_COMMENT_LENGTH} characters.")

    review = db.session.scalar(
        db.select(Review).where(Review.customer_id == customer.id, Review.product_id == product.id)
    )
    if review is None:
        review = Review(tenant_id=product.tenant_id, product_id=product.id, customer_id=customer.id)
        db.session.add(review)
    review.rating, review.comment = rating, comment
    db.session.commit()
    return review


def _public(review: Review) -> dict:
    # First name only: a review is public, the customer's full name is not.
    return {
        "name": review.customer.name.split()[0],
        "rating": review.rating,
        "comment": review.comment,
        "reviewed_at": review.created_at.isoformat(),
    }
