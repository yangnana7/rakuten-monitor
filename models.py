#!/usr/bin/env python3
"""
楽天商品監視システム データベースモデル定義
"""

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import enum
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class ChangeType(enum.Enum):
    NEW = "NEW"
    RESTOCK = "RESTOCK" 
    TITLE_UPDATE = "TITLE_UPDATE"
    PRICE_UPDATE = "PRICE_UPDATE"
    SOLDOUT = "SOLDOUT"

class Item(Base):
    """商品の現在状態"""
    __tablename__ = 'items'
    
    code = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    price = Column(Integer)
    in_stock = Column(Boolean, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # リレーション
    changes = relationship("Change", back_populates="item")

class Change(Base):
    """変更イベント履歴"""
    __tablename__ = 'changes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, ForeignKey('items.code'), nullable=False)
    type = Column(Enum(ChangeType), nullable=False)
    payload = Column(Text)  # SQLiteではJSONBの代わりにTextを使用
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # リレーション
    item = relationship("Item", back_populates="changes")

class Run(Base):
    """実行メタデータ"""
    __tablename__ = 'runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    snapshot = Column(Text)  # ファイルパスまたはJSONデータ

# データベース接続設定
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///rakuten_monitor.db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """データベースセッションを取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """テーブルを作成"""
    Base.metadata.create_all(bind=engine)