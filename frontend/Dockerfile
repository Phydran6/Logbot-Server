# Node 20 ist seit April 2026 ohne Sicherheitsupdates - gebaut wird mit der
# aktuellen LTS-Fassung. Ausgeliefert wird nur das fertige Bundle ueber nginx.
FROM node:24-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:alpine
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
