# sela_backend.py
# مشروع: صلة (Sela) - ربط المغترب بالتاجر السوداني
# التشغيل: pip install fastapi uvicorn sqlalchemy pydantic
# ثم: uvicorn sela_backend:app --reload

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, List
import datetime

# ==========================================
# 1. إعداد قاعدة البيانات (SQLite للمشروع الأولي)
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./sela.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 2. جداول قاعدة البيانات (Models)
# ==========================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, unique=True, index=True)
    country = Column(String)
    balance = Column(Float, default=0.0)

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, unique=True, index=True)
    location = Column(String)
    is_verified = Column(Boolean, default=False)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer)
    merchant_id = Column(Integer)
    amount = Column(Float)
    service_details = Column(String)
    receipt_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ==========================================
# 3. مخططات البيانات (Pydantic Schemas)
# ==========================================
class UserCreate(BaseModel):
    name: str
    phone: str
    country: str

class MerchantCreate(BaseModel):
    name: str
    phone: str
    location: str

class TransactionCreate(BaseModel):
    sender_phone: str
    merchant_phone: str
    amount: float
    service_details: str

class TransactionUpdate(BaseModel):
    status: str

class DepositRequest(BaseModel):
    phone: str
    amount: float

# ==========================================
# 4. إعداد التطبيق والـ CORS
# ==========================================
app = FastAPI(title="Sela API", description="واجهة برمجة تطبيقات صلة للتحويلات العكسية")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# 5. دوال الذكاء الاصطناعي والواتساب (Mock/Placeholder)
# ==========================================
def verify_receipt_with_ai(receipt_url: str) -> bool:
    print(f"🤖 جاري تحليل الفاتورة: {receipt_url}")
    return True

def send_whatsapp_notification(phone: str, message: str):
    print(f"📱 رسالة واتساب إلى {phone}: {message}")

# ==========================================
# 6. نقاط النهاية (API Endpoints)
# ==========================================
@app.get("/")
def home():
    return {"message": "مرحباً بك في API منصة صلة (Sela)"}

@app.post("/register/user")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.phone == user.phone).first()
    if db_user:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
    new_user = User(name=user.name, phone=user.phone, country=user.country)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "تم تسجيل المغترب بنجاح", "user_id": new_user.id}

@app.post("/register/merchant")
def register_merchant(merchant: MerchantCreate, db: Session = Depends(get_db)):
    db_merchant = db.query(Merchant).filter(Merchant.phone == merchant.phone).first()
    if db_merchant:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل مسبقاً")
    new_merchant = Merchant(name=merchant.name, phone=merchant.phone, location=merchant.location, is_verified=True)
    db.add(new_merchant)
    db.commit()
    db.refresh(new_merchant)
    return {"message": "تم تسجيل التاجر بنجاح", "merchant_id": new_merchant.id}

@app.post("/deposit")
def deposit(request: DepositRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    user.balance += request.amount
    db.commit()
    return {"message": f"تم إيداع {request.amount} بنجاح", "new_balance": user.balance}

@app.post("/create-transaction")
def create_transaction(tx: TransactionCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    sender = db.query(User).filter(User.phone == tx.sender_phone).first()
    merchant = db.query(Merchant).filter(Merchant.phone == tx.merchant_phone).first()
    
    if not sender or not merchant:
        raise HTTPException(status_code=404, detail="المغترب أو التاجر غير موجود")
    
    if sender.balance < tx.amount:
        raise HTTPException(status_code=400, detail="الرصيد غير كافٍ. يرجى إيداع المبلغ أولاً.")
    
    sender.balance -= tx.amount
    
    new_tx = Transaction(
        sender_id=sender.id,
        merchant_id=merchant.id,
        amount=tx.amount,
        service_details=tx.service_details,
        status="pending"
    )
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    
    background_tasks.add_task(
        send_whatsapp_notification, 
        merchant.phone, 
        f"طلب دفع جديد بقيمة {tx.amount} لـ {tx.service_details}. يرجى التأكيد."
    )
    
    return {"message": "تم إنشاء طلب الدفع بنجاح", "transaction_id": new_tx.id, "status": new_tx.status}

@app.post("/confirm-transaction/{tx_id}")
def confirm_transaction(tx_id: int, receipt_url: str, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="العملية غير موجودة")
    
    tx.receipt_url = receipt_url
    is_valid = verify_receipt_with_ai(receipt_url)
    if is_valid:
        tx.status = "completed"
        message = "تم التحقق من الفاتورة وإتمام العملية بنجاح"
    else:
        tx.status = "rejected"
        message = "فشل التحقق من الفاتورة. يرجى إعادة الإرسال."
        
    db.commit()
    
    sender = db.query(User).filter(User.id == tx.sender_id).first()
    send_whatsapp_notification(sender.phone, f"تمت عملية الدفع الخاصة بك: {message}")
    
    return {"message": message, "status": tx.status}

@app.get("/transactions/{user_phone}")
def get_user_transactions(user_phone: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == user_phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    txs = db.query(Transaction).filter(Transaction.sender_id == user.id).all()
    return {"user": user.name, "transactions": txs}
