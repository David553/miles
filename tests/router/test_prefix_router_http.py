import asyncio
import httpx
from miles.router.config import MilesRouterConfig
from miles.router.router import MilesRouter


def test_actual_router_forwards_payload_and_cleans_failure_counts():
 async def run():
  router=MilesRouter(MilesRouterConfig(host='127.0.0.1',port=30380,max_connections=32,timeout=10,health_check_interval=60,health_check_failure_threshold=3,prefix_affinity=True))
  await router.client.aclose()
  seen=[]
  async def backend(req):
   seen.append(req)
   if req.headers.get('x-test-fail'):raise httpx.ConnectError('test failure',request=req)
   return httpx.Response(200,json={'worker':req.url.host},request=req)
  router.client=httpx.AsyncClient(transport=httpx.MockTransport(backend))
  try:
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=router.app),base_url='http://router') as client:
    for worker in ('http://a','http://b'):
     assert (await client.post('/add_worker',json={'url':worker})).status_code==200
    body={'input_ids':list(range(129)),'return_logprob':True,'sampling_params':{'max_new_tokens':8}}
    router.worker_request_counts['http://a']=1
    r=await client.post('/generate',json=body);assert r.json()['worker']=='b'
    router.worker_request_counts['http://a']=0
    r=await client.post('/generate',json=body);assert r.json()['worker']=='b'
    assert __import__('json').loads(seen[-1].content)==body
    try:await client.post('/generate',json=body,headers={'x-test-fail':'1'})
    except httpx.ConnectError:pass
    assert router.worker_request_counts=={'http://a':0,'http://b':0}
    await client.post('/remove_worker',json={'url':'http://b'})
    assert (await client.post('/generate',json=body)).json()['worker']=='a'
  finally:await router.client.aclose()
 asyncio.run(run())
