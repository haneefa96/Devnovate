FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY src ./src
COPY index.html vite.config.ts tailwind.config.ts tsconfig.json tsconfig.node.json postcss.config.js ./

# Build the application
RUN npm run build

# Expose port
EXPOSE 5173

# Run the application
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
