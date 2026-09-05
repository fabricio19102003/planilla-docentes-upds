from pydantic import BaseModel
class WhatsAppPreferenceResponse(BaseModel):
 teacher_ci:str; phone_e164:str; is_verified:bool; consent_revision:int
