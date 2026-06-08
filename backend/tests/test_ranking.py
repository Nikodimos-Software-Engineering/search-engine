import pytest
import numpy as np
from indexer import SearchIndex


@pytest.fixture
def index():
    idx = SearchIndex()
    idx.documents = []
    return idx


def make_doc(title, content, url=None):
    if url is None:
        url = f"http://example.com/{abs(hash(content))}"
    return {"url": url, "title": title, "content": content}


class TestSearchIndex:

    def test_idf_decreases_with_term_frequency(self, index):
        docs = [
            make_doc("Doc1", "apple banana cherry"),
            make_doc("Doc2", "apple banana date"),
            make_doc("Doc3", "apple banana fig"),
        ]
        index.documents = docs
        index.build_index()

        assert index.idf[index.vocabulary["apple"]] < index.idf[index.vocabulary["cherry"]]
        assert index.idf[index.vocabulary["banana"]] < index.idf[index.vocabulary["date"]]

    def test_cosine_similarity_identical_vectors(self, index):
        docs = [
            make_doc("Doc", "python programming language"),
            make_doc("Doc", "python programming language"),
        ]
        index.documents = docs
        index.build_index()

        vec1 = index.tfidf_matrix[0]
        vec2 = index.tfidf_matrix[1]
        similarity = float(np.dot(vec1, vec2))
        assert similarity == pytest.approx(1.0, abs=1e-6)

    def test_title_weighted_ranks_higher(self, index):
        docs = [
            make_doc("Python Tutorial", "some other content here"),
            make_doc("Other Topic", "python is a programming language used for web development"),
        ]
        index.documents = docs
        index.build_index()

        results = index.search("python")
        assert len(results) >= 1
        assert results[0]["title"] == "Python Tutorial"

    def test_query_expansion_substring_matching(self, index):
        docs = [
            make_doc("Dictionary", "this document talks about dictionary data structures in python"),
        ]
        index.documents = docs
        index.build_index()

        results = index.search("dict")
        assert len(results) >= 1

        snippet_lower = results[0]["snippet"].lower()
        title_lower = results[0]["title"].lower()
        assert "dictionary" in snippet_lower or "dictionary" in title_lower
