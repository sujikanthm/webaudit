# Step 1: Base image
FROM python:3.11-slim

# Step 2: Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Step 3: Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs

# Step 4: Set the working directory
WORKDIR /app

# --- OPTIMIZATION START ---
# Step 5: Copy ONLY the files needed for dependency installation first.
# This allows Docker to cache these layers even if the app code changes.
COPY requirements.txt .

# Step 6: Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 7: Install Lighthouse and Playwright browsers
# This layer will also be cached as long as requirements.txt doesn't change.
RUN npm install -g lighthouse \
    && python -m playwright install --with-deps

# Step 8: NOW, copy the rest of the application code.
# This ensures that changes to app.py only invalidate this layer and the ones after it.
COPY . .
# --- OPTIMIZATION END ---

# Step 9: Expose the Streamlit port
EXPOSE 8501

# Step 10: Define the command to run when the container starts
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]