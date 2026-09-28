# Imagen de DESARROLLO del frontend (la de producción se hará en su fase).
FROM node:22-alpine

WORKDIR /app

# Primero las dependencias: esta capa solo se reconstruye si cambian package*.json.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
