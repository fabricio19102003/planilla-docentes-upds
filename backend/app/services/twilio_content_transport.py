import httpx
from app.services.whatsapp_service import WhatsAppSendResult
class TwilioContentTransport:
 def __init__(self,account_sid,api_key_sid,api_key_secret,from_number,status_callback,*,api_base_url='https://api.twilio.com',timeout_seconds=3.0,client=None):self.account_sid,self.auth,self.from_number,self.status_callback,self.api_base_url,self.timeout_seconds,self.client=account_sid,(api_key_sid,api_key_secret),from_number,status_callback,api_base_url.rstrip('/'),timeout_seconds,client
 def send(self,*,to,content_sid,content_variables):
  if not content_sid or not content_variables or not self.status_callback:return WhatsAppSendResult(status='failed',error_code='official_content_contract_invalid')
  p={'From':f'whatsapp:{self.from_number}','To':f'whatsapp:{to}','ContentSid':content_sid,'ContentVariables':content_variables,'StatusCallback':self.status_callback};u=f'{self.api_base_url}/2010-04-01/Accounts/{self.account_sid}/Messages.json'
  try:
   if self.client:r=self.client.post(u,auth=self.auth,data=p)
   else:
    with httpx.Client(timeout=self.timeout_seconds) as c:r=c.post(u,auth=self.auth,data=p)
  except httpx.ConnectError:return WhatsAppSendResult(status='failed',error_code='twilio_connect_error')
  except httpx.RequestError:return WhatsAppSendResult(status='ambiguous',error_code='twilio_delivery_ambiguous')
  if 200<=r.status_code<300:
   try:sid=r.json().get('sid')
   except ValueError:sid=None
   return WhatsAppSendResult(status='sent',provider_message_id=str(sid) if sid else None)
  return WhatsAppSendResult(status='failed',error_code=f'twilio_http_{r.status_code}')
