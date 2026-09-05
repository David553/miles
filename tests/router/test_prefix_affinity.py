import json
from miles.router.prefix_affinity import PrefixAffinity, request_prefixes

def prefix(tokens, **kw):
 return request_prefixes(json.dumps({'input_ids':tokens,**kw}).encode())

def test_repeated_and_growing_tokens_choose_known_worker():
 p=PrefixAffinity();a=prefix(list(range(129)))
 p.remember('b',a,epoch=p.epoch)
 assert p.choose({'a':0,'b':0},prefix(list(range(150))))=='b'
 assert p.choose({'a':0,'b':0},prefix([400]*129))=='a'

def test_overload_spill_and_dead_worker():
 p=PrefixAffinity(max_load_skew=2);a=prefix(list(range(129)))
 p.remember('b',a,epoch=0)
 assert p.choose({'a':0,'b':2},a)=='b'
 assert p.choose({'a':0,'b':3},a)=='a'
 p.remove_worker('b');p.remember('b',a,epoch=0)
 assert p.choose({'a':0,'b':0},a)=='a'

def test_ttl_bound_and_inflight_flush():
 t=[0];p=PrefixAffinity(max_entries=2,ttl=2,clock=lambda:t[0]);a=prefix(list(range(129)))
 p.remember('b',a,epoch=0);assert len(p.entries)==2
 t[0]=3;assert p.choose({'a':0,'b':0},a)=='a';assert not p.entries
 p.clear();p.remember('b',a,epoch=0);assert not p.entries

def test_namespace_and_invalid_requests():
 a=prefix(list(range(129)),lora_path='a')
 assert a!=prefix(list(range(129)),lora_path='b')
 assert not prefix(list(range(129)),image_data=['image'])
 for tokens in ([True],[-1],[2**32],[[1,2]],'text'):
  assert not prefix(tokens)
 assert not request_prefixes(b'null')
 assert not request_prefixes(b'broken')
 assert not prefix(list(range(32)))
 assert len(prefix(list(range(33))))==1
