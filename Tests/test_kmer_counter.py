import unittest
import shutil
import tempfile
import lmdb
import numpy as np
from kmer_counter import count_kmers, get_counts, add_counts, get_kmer_names

def create_temp_files():
    directory = tempfile.mkdtemp()
    db = directory + '/TEMPdatabase'
    with open(directory + '/A1', 'w') as f:
        f.write('>\nAAACCCCAA')
    with open(directory + '/A2', 'w') as f:
        f.write('>\nAACCCCAA')
    with open(directory + '/B1', 'w') as f:
        f.write('>\nAACCAACC')
    files = [directory+'/A1', directory+'/A2', directory+'/B1']
    return directory, db, files


class CountKmers(unittest.TestCase):
    def setUp(self):
        self.dir, self.db, self.files = create_temp_files()
        count_kmers(2, 1, self.files, self.db)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_A1(self):
        count1 = 0
        count2 = 0
        env = lmdb.open('%s'%self.db, max_dbs=100)
        A1 = env.open_db(self.dir+'/A1')
        with env.begin(write=False, db=A1) as txn:
            with txn.cursor() as cursor:
                for key, val in cursor:
                    count2 += 1
                    if key == 'AA' and val == '3':
                        count1 += 1
                    elif key =='AC' and val == '1':
                        count1 += 1
                    elif key == 'CA' and val == '1':
                        count1 += 1
                    elif key == 'CC' and val == '3':
                        count1 += 1
        self.assertEqual(count1, count2)

    def test_A2(self):
        count1 = 0
        count2 = 0
        env = lmdb.open('%s'%self.db, max_dbs=100)
        A2 = env.open_db(self.dir+'/A2')
        with env.begin(write=False, db=A2) as txn:
            with txn.cursor() as cursor:
                for key, val in cursor:
                    count2 += 1
                    if key == 'AA' and val == '2':
                        count1 += 1
                    elif key =='AC' and val == '1':
                        count1 += 1
                    elif key == 'CA' and val == '1':
                        count1 += 1
                    elif key == 'CC' and val == '3':
                        count1 += 1
        self.assertEqual(count1, count2)

    def test_B1(self):
        count1 = 0
        count2 = 0
        env = lmdb.open('%s'%self.db, max_dbs=100)
        B1 = env.open_db(self.dir+'/B1')
        with env.begin(write=False, db=B1) as txn:
            with txn.cursor() as cursor:
                for key, val in cursor:
                    count2 += 1
                    if key == 'AA' and val == '2':
                        count1 += 1
                    elif key =='AC' and val == '2':
                        count1 += 1
                    elif key == 'CA' and val == '1':
                        count1 += 1
                    elif key == 'CC' and val == '2':
                        count1 += 1
        self.assertEqual(count1, count2)


class GetCounts(unittest.TestCase):
    def setUp(self):
        self.dir, self.db, self.files = create_temp_files()
        count_kmers(2, 1, self.files, self.db)
        self.counts = get_counts(self.files, self.db)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_dimensions(self):
        self.assertEqual(3, len(self.counts))

    def test_values(self):
        val = True
        val = val and np.array_equal(self.counts[0], [3,1,1,3])
        val = val and np.array_equal(self.counts[1], [2,1,1,3])
        val = val and np.array_equal(self.counts[2], [2,2,1,2])
        self.assertTrue(val)


class AddCounts(unittest.TestCase):
    def setUp(self):
        self.dir, self.db, self.files = create_temp_files()
        count_kmers(2, 1, self.files, self.db)
        self.new_file = self.dir + '/B2'
        with open(self.new_file, 'w') as f:
            f.write('>\nAAAAAAT')
        add_counts([self.new_file], self.db)
        output_files = self.files + [self.new_file]
        self.counts = get_counts(output_files, self.db)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_dimensions(self):
        self.assertEqual(4, len(self.counts))

    def test_values(self):
        val = True
        val = val and np.array_equal(self.counts[0], [3,1,1,3])
        val = val and np.array_equal(self.counts[1], [2,1,1,3])
        val = val and np.array_equal(self.counts[2], [2,2,1,2])
        val = val and np.array_equal(self.counts[3], [5,0,0,0])
        self.assertTrue(val)


class GetKmerNames(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp() + '/'
        self.fasta = self.dir + 'TEMP.fasta'
        self.db = self.dir + 'TEMPDB'
        with open(self.fasta, 'w') as f:
            f.write('>label1\nATAT\n>label2\nCGCG\n>label3\nAAAA\n>label4\nAGGA\n>label5\nCGCG')
        count_kmers(4, 0, [self.fasta], self.db)
        self.names = get_kmer_names(self.db)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_names(self):
        correct_names = np.array(['AAAA', 'AGGA', 'ATAT', 'CGCG'])
        if np.array_equal(correct_names, self.names):
            val = True
        else:
            val = False
        self.assertTrue(val)


if __name__=="__main__":
    loader = unittest.TestLoader()
    all_tests = loader.discover('.', pattern='test_kmer_counter.py')
    runner = unittest.TextTestRunner()
    runner.run(all_tests)
