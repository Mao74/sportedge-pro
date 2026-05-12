# syntax=docker/dockerfile:1.7
# Dev image — runs the Vite dev server with HMR. Production multi-stage
# (build + Caddy) lands in step 15.
FROM node:20-alpine

WORKDIR /app

# Install dependencies first to keep this layer cached.
COPY package.json ./
# package-lock.json is created on first `npm install` inside the container
# during dev; production build will rely on a committed lockfile.
RUN npm install --no-audit --no-fund

# Copy the rest of the project. In dev the host volume overrides this.
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
