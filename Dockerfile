# ใช้ Python ตัวเลือกแบบเบา (slim)
FROM python:3.11-slim

# กำหนดโฟลเดอร์ทำงานภายใน Container
WORKDIR /app

# คัดลอกไฟล์จัดการ Dependencies เข้าไปในระบบ
COPY requirements.txt .

# ติดตั้งแพ็กเกจ
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ดทั้งหมดเข้า Container
COPY . .

# เปิดพอร์ตใช้งานระบบเป็น 2100
EXPOSE 2100

# รันแอปพลิเคชัน
CMD ["python", "open_app.py"]