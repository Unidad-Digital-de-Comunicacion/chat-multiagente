FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
# Vite incrusta las variables VITE_* en el bundle en build-time, no en
# runtime — por eso va como build ARG (docker-compose.yml lo pasa en
# `build.args`), no como `environment` del contenedor final.
ARG VITE_CORE_API_URL=http://localhost:8001
ENV VITE_CORE_API_URL=$VITE_CORE_API_URL
ARG VITE_CONVERSATION_ENGINE_URL=http://localhost:8003
ENV VITE_CONVERSATION_ENGINE_URL=$VITE_CONVERSATION_ENGINE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
