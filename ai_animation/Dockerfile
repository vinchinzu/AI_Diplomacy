# vite-server/Dockerfile
FROM node:20.4.0-alpine

# Create app directory
WORKDIR /app

# Copy package.json and lock file first for better caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Now copy everything else
COPY . .

# Accept build arguments for environment variables
ARG VITE_ELEVENLABS_API_KEY
ARG VITE_WEBHOOK_URL
ARG VITE_STREAMING_MODE
ARG VITE_DEBUG_MODE
ARG VITE_INSTANT_MODE

# Set environment variables for the build
ENV VITE_ELEVENLABS_API_KEY=$VITE_ELEVENLABS_API_KEY
ENV VITE_WEBHOOK_URL=$VITE_WEBHOOK_URL
ENV VITE_STREAMING_MODE=$VITE_STREAMING_MODE
ENV VITE_DEBUG_MODE=$VITE_DEBUG_MODE
ENV VITE_INSTANT_MODE=$VITE_INSTANT_MODE

# Build the production-ready files (dist/)
RUN npm run build

# Expose the port that `npm run preview` uses (default is 4173)
EXPOSE 4173

# Finally, serve the built app
CMD ["npm", "run", "preview"]

