from datetime import datetime
import re
from sqlalchemy import Boolean,DateTime,ForeignKey,Integer,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base
class WhatsAppPreference(Base):
 __tablename__='whatsapp_preferences'
 teacher_ci:Mapped[str]=mapped_column(String(20),ForeignKey('teachers.ci',ondelete='CASCADE'),primary_key=True)
 phone_e164:Mapped[str]=mapped_column(String(16),nullable=False)
 is_verified:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
 consent_evidence:Mapped[str|None]=mapped_column(Text)
 consent_revision:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 opt_out_evidence:Mapped[str|None]=mapped_column(Text)
 opted_out_at:Mapped[datetime|None]=mapped_column(DateTime)
 @staticmethod
 def canonical_e164(v):
  v=v.strip() if isinstance(v,str) else ''
  return v if re.fullmatch(r'\+[1-9]\d{7,14}',v) else None
 @property
 def is_eligible_for_whatsapp(self): return bool(self.canonical_e164(self.phone_e164) and self.is_verified and self.consent_evidence and not self.opted_out_at)
 def record_consent(self,e): self.consent_evidence=e;self.opted_out_at=None;self.consent_revision+=1
 def record_opt_out(self,e): self.opt_out_evidence=e;self.opted_out_at=datetime.utcnow();self.consent_revision+=1
