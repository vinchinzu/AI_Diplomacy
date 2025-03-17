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

# Build the production-ready files (dist/)
#RUN npm run build

# Expose the port that `npm run preview` uses (default is 4173)
EXPOSE 4173

# Finally, serve the built app
CMD ["npm", "run", "preview"]

