import numpy as np
import json
import re
import math
from collections import Counter, defaultdict
from database import Document, SessionLocal


class SearchIndex:
    def __init__(self):
        self.documents = []
        self.vocabulary = {}
        self.idf = None
        self.tfidf_matrix = None
        self.is_built = False
        self.all_words = set()

    def tokenize(self, text):
        text = text.lower()
        text = re.sub(r'[^a-z\s]', ' ', text)
        words = [w for w in text.split() if len(w) > 2]
        return words

    def compute_tf(self, words):
        counts = Counter(words)
        total = len(words)
        if total == 0:
            return {}
        return {word: count / total for word, count in counts.items()}

    def expand_query(self, query_words):
        expanded = set(query_words)
        for query_word in query_words:
            for vocab_word in self.all_words:
                if query_word in vocab_word and query_word != vocab_word:
                    expanded.add(vocab_word)
        return list(expanded)

    def add_documents(self, documents):
        db = SessionLocal()
        try:
            for doc in documents:
                content = doc.get("content", "")
                if len(content) > 50:
                    existing = db.query(Document).filter_by(url=doc["url"]).first()
                    if not existing:
                        db_doc = Document(
                            url=doc["url"],
                            title=doc.get("title", ""),
                            content=content,
                            domain=doc["url"].split("/")[2],
                            word_count=len(content.split())
                        )
                        db.add(db_doc)
            db.commit()
        finally:
            db.close()

        for doc in documents:
            content = doc.get("content", "")
            if len(content) > 50:
                self.documents.append({
                    "url": doc["url"],
                    "title": doc.get("title", ""),
                    "content": content,
                    "snippet": content[:300] + "..." if len(content) > 300 else content
                })

    def load_from_db(self):
        db = SessionLocal()
        try:
            db_docs = db.query(Document).all()
            self.documents = []
            for doc in db_docs:
                self.documents.append({
                    "url": doc.url,
                    "title": doc.title,
                    "content": doc.content,
                    "snippet": doc.content[:300] + "..." if len(doc.content) > 300 else doc.content
                })
            print(f"Loaded {len(self.documents)} documents from database")
        finally:
            db.close()

    def build_index(self):
        if not self.documents:
            return
        all_tokens = []
        doc_term_freqs = []
        for doc in self.documents:
            text = f"{doc['title']} {doc['title']} {doc['content']}"
            words = self.tokenize(text)
            all_tokens.extend(words)
            doc_term_freqs.append(self.compute_tf(words))
        unique_terms = sorted(set(all_tokens))
        self.vocabulary = {term: idx for idx, term in enumerate(unique_terms)}
        self.all_words = set(unique_terms)
        vocab_size = len(unique_terms)
        num_docs = len(self.documents)
        doc_freq = defaultdict(int)
        for tf_dict in doc_term_freqs:
            for word in tf_dict:
                doc_freq[word] += 1
        self.idf = np.zeros(vocab_size)
        for word, idx in self.vocabulary.items():
            self.idf[idx] = math.log((num_docs + 1) / (doc_freq[word] + 1)) + 1
        self.tfidf_matrix = np.zeros((num_docs, vocab_size))
        for doc_idx, tf_dict in enumerate(doc_term_freqs):
            for word, tf in tf_dict.items():
                word_idx = self.vocabulary[word]
                self.tfidf_matrix[doc_idx, word_idx] = tf * self.idf[word_idx]
        norms = np.linalg.norm(self.tfidf_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.tfidf_matrix = self.tfidf_matrix / norms
        self.is_built = True
        print(f"Index built: {num_docs} docs, {vocab_size} terms")

    def search(self, query, top_k=10):
        if not self.is_built or not self.documents:
            return []
        query_words = self.tokenize(query)
        if not query_words:
            return []
        expanded_words = self.expand_query(query_words)
        query_tf = self.compute_tf(expanded_words)
        query_vec = np.zeros(len(self.vocabulary))
        for word, tf in query_tf.items():
            if word in self.vocabulary:
                idx = self.vocabulary[word]
                query_vec[idx] = tf * self.idf[idx]
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec = query_vec / query_norm
        similarities = self.tfidf_matrix.dot(query_vec)
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.001:
                doc = self.documents[idx]
                results.append({
                    "url": doc["url"],
                    "title": doc["title"],
                    "snippet": self.generate_snippet(doc["content"], query),
                    "score": round(score, 4)
                })
        return results

    def generate_snippet(self, content, query, max_length=200):
        query_terms = query.lower().split()
        content_lower = content.lower()
        best_pos = 0
        for term in query_terms:
            pos = content_lower.find(term)
            if pos != -1:
                best_pos = pos
                break
        start = max(0, best_pos - 100)
        end = min(len(content), best_pos + max_length)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet

    def save(self, filepath):
        data = {
            "vocabulary": self.vocabulary,
            "all_words": list(self.all_words),
            "idf": self.idf.tolist() if self.idf is not None else None,
            "tfidf_matrix": self.tfidf_matrix.tolist() if self.tfidf_matrix is not None else None
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)

    def load(self, filepath):
        import os
        if not os.path.exists(filepath):
            return
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.vocabulary = data["vocabulary"]
        self.all_words = set(data.get("all_words", []))
        if data["idf"]:
            self.idf = np.array(data["idf"])
        if data["tfidf_matrix"]:
            self.tfidf_matrix = np.array(data["tfidf_matrix"])
            self.is_built = True
        self.load_from_db()
