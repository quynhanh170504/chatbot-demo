# Sử dụng Python phiên bản ổn định và nhẹ
FROM python:3.11-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Copy file requirements trước để tận dụng Docker cache
COPY requirements.txt .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Tạo thư mục chứa bài viết nếu chưa có
RUN mkdir -p articles_md

# Lệnh chạy script (Khi chạy Docker, ta truyền API Key qua biến môi trường)
CMD ["python", "main.py"]