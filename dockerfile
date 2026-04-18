FROM node:25.8.1-alpine3.23 AS build

WORKDIR /app
COPY . .

RUN npm ci
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
