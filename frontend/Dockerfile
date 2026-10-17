# StyleMate frontend: build the Vue app, then serve it with nginx, which also passes /api to Flask.

# Stage 1: build. Node is needed only here and isn't in the final image.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve the built files
FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
