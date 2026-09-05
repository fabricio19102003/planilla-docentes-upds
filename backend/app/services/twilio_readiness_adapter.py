from typing import Any
class TwilioReadinessAdapter:
 def evaluate(self,facts:dict[str,Any])->dict[str,Any]:
  c=facts.get('capacity'); available=isinstance(c,dict) and bool(c.get('available')); ready=all((facts.get('official_enabled'),facts.get('dispatch_enabled'),facts.get('sender_status')=='ONLINE',facts.get('templates_approved'),facts.get('credentials_valid'),facts.get('canonical_callback'),available)); return {'ready':ready,'capacity':c if available else {'available':False},'reason':None if ready else 'official_readiness_unavailable'}
