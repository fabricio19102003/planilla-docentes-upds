FROM node:22.14.0-alpine3.21 AS build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27.4-alpine3.21

COPY deploy/nginx/app-nginx.conf /etc/nginx/nginx.conf
COPY --from=build --chown=101:101 /app/frontend/dist/ /usr/share/nginx/html/

USER 101:101
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
