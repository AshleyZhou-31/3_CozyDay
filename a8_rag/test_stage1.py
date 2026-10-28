import unittest
from chunking import (load_knowledge_base, validate_knowledge_base, build_all_chunks,
                      fixed_length_chunks, overlapping_paragraph_chunks, hybrid_topic_chunks,
                      validate_chunks)

class Stage1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=load_knowledge_base()
    def test_dataset(self):
        s=validate_knowledge_base(self.data)
        self.assertEqual(s['paragraphs'],30)
        self.assertGreaterEqual(s['total_words'],2000)
    def test_all_chunkers(self):
        for name,chunks in build_all_chunks(self.data).items():
            self.assertTrue(validate_chunks(self.data,chunks,name))
    def test_overlap_pairs(self):
        chunks=overlapping_paragraph_chunks(self.data)
        self.assertEqual(len(chunks),len(self.data)-1)
        self.assertEqual(chunks[0]['source_ids'],['P001','P002'])
        self.assertEqual(chunks[1]['source_ids'],['P002','P003'])
    def test_hybrid_no_cross_topic(self):
        chunks=hybrid_topic_chunks(self.data)
        lookup={r['id']:r['topic'] for r in self.data}
        for chunk in chunks:
            self.assertEqual({lookup[sid] for sid in chunk['source_ids']},{chunk['topic']})
    def test_fixed_preserves_all_sentences(self):
        self.assertTrue(validate_chunks(self.data,fixed_length_chunks(self.data),'fixed'))
    def test_duplicate_ids_fail(self):
        malformed=[dict(r) for r in self.data]
        malformed[1]['id']=malformed[0]['id']
        with self.assertRaises(AssertionError): validate_knowledge_base(malformed)
    def test_bad_paragraph_length_fail(self):
        malformed=[dict(r) for r in self.data]
        malformed[0]['body']='Too short.'
        with self.assertRaises(AssertionError): validate_knowledge_base(malformed)

if __name__ == '__main__': unittest.main(verbosity=2)
