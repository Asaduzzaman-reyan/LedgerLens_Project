import json
import threading
import numpy as np

class Embeddings:
    def __init__(self, settings):
        self.settings = settings
        self.model = None
        self.lock = threading.Lock()
    def encode(self, texts):
        if self.settings.embeddings == 'off':
            return [None for _ in texts]
        with self.lock:
            if self.model is None:
                from fastembed import TextEmbedding
                self.model = TextEmbedding('BAAI/bge-small-en-v1.5',cache_dir=str(self.settings.data/'models'),threads=2)
            return [v.tolist() for v in self.model.embed(texts)]
    def search(self, db, query, limit):
        vector = self.encode([query])[0]
        if vector is None:
            raise ValueError('Semantic search disabled; enable DOCINT_EMBEDDINGS=fastembed')
        v = np.asarray(vector)
        scores = {}
        with db.connect() as con:
            for row in con.execute('SELECT document_id,source,text,vector FROM units WHERE vector IS NOT NULL'):
                x = np.asarray(json.loads(row['vector']))
                score = float(np.dot(x,v)/(np.linalg.norm(x)*np.linalg.norm(v)+1e-12))
                if row['document_id'] not in scores or score>scores[row['document_id']]['score']:
                    scores[row['document_id']] = {'id':row['document_id'],'score':round(score,5),'source':row['source'],'snippet':row['text'][:240]}
        return sorted(scores.values(),key=lambda r:r['score'],reverse=True)[:limit]
