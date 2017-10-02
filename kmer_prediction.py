import subprocess
from sklearn import svm
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.model_selection import StratifiedShuffleSplit as ssSplit
import os
import lmdb
import sys

def start(filename, k, limit, env, txn, data):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Performs a kmer count on filename, counting kmers witha length of k and
    removing any kmer that has a count less than limit. Clears the database
    data and then writes each kmer as a key with value -1 to data.

    Returns a lexicographically sorted list of lists. Where each element in the
    outer list has a first element that is a kmer and a second element that is
    the count corresponding to that kmer.
    """
    args = ['jellyfish', 'count', '-m', '%d' % k, '-s', '10M', '-t', '30', '-C',
            '%s' % filename, '-o', 'test.jf', '-L', '%d' % limit]
    p = subprocess.Popen(args, bufsize=-1)
    p.communicate()
    # Get results from kmer count
    args = ['jellyfish', 'dump', '-c', 'test.jf']
    p = subprocess.Popen(args, bufsize=-1, stdout=subprocess.PIPE)
    out, err = p.communicate()
    # Transform results into usable format
    arr = [x.split(' ') for x in out.split('\n') if x]

    txn.drop(data)
    current = env.open_db('%s'%filename)
    for line in arr:
        txn.put(line[0], line[1])
        txn.put(line[0], line[1], db=current)

def firstpass(filename, k, limit, evn, txn):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Performs a kmer count on filename, counting kmers with a length of k and
    removing any kmer that has a count less than limit. Only saves kmers that
    are already present in the database that txn points to. Removes any kmer
    from the databse that is not present in filename.

    Returns a list with the same specifications as the list returned by
    kmer_prediction.start()
    """
    args = ['jellyfish', 'count', '-m', '%d' % k, '-s', '10M', '-t', '30', '-C',
            '%s' % filename, '-o', 'test.jf', '-L', '%d' % limit]
    p = subprocess.Popen(args, bufsize=-1)
    p.communicate()
    # Get results from kmer count
    args = ['jellyfish', 'dump', '-c', 'test.jf']
    p = subprocess.Popen(args, bufsize=-1, stdout=subprocess.PIPE)
    out, err = p.communicate()
    # Transform results into usable format
    arr = [x.split(' ') for x in out.split('\n') if x]

    current = env.open_db('%s'%filename)

    for line in arr:
        if txn.get(line[0], default=False):
            txn.put(line[0], line[1], overwrite=True, dupdata=False)

    cursor = txn.cursor()
    for key, value in cursor:
        if value == '-1':
            txn.delete(key)
        else:
            txn.put(key, value, db=current)
            txn.put(key, '-1')

def second_start(arr, k, evn, txn, data):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Clears the database data and then writes every kmer present in arr to the
    database.

    Returns a list of lexicographically sorted kmer counts. The kmers themselves
    are not output, instead index 0 holds the count for the lexicographically
    smallest kmer and index 1 holds the count for the next lexicagraphically
    smallest kmer etc.
    """
    txn.drop(data)
    for line in arr:
        txn.put(line[0], line[1])
    array = []
    cursor = txn.cursor()
    for key, value in cursor:
        array.append(int(value))

    return array

def secondpass(arr, k, evn, txn):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Removes every kmer from arr that is not present in the database pointed to
    by txn.

    Returns a list of the same specifications as the list returned by
    kmer_prediction.second_satart()
    """
    for line in arr:
        if txn.get(str(line[0]), default=False):
            txn.put(line[0], line[1], overwrite=True, dupdata=False)

    array = []
    cursor = txn.cursor()
    for key, value in cursor:
        array.append(int(value))

    return array

def print_status(counter, total):
    """
    Outputs a progress bar.
    """
    percent = (counter*100)/total
    sys.stdout.write('\r')
    sys.stdout.write("[%-44s] %d%%" % ('='*((percent*44)/100), percent))
    sys.stdout.flush()

def set_up_files(filepath):
    """
    Helper method for running kmer_prediction.py from the command line.

    Takes a path to a directory, returns a list of the complete paths to each
    file in the directory
    """
    if not filepath[-1] == '/':
        filepath += '/'
    return [filepath + x for x in os.listdir(filepath)]

def setup_data(files, k, limit, txn, data):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Takes a list of paths to fasta files, a kmer length, a lower limit on how
    many times a kmer needs to occur in order for it to be output, and an lmdb
    transaction and corresponding database.

    Returns a list where each element of the list is a list of kmer counts for a
    genome contained in one of the fasta files.
    """
    counter = 0
    total = len(files)

    arrays = []
    arrays.append(start(files[0], k, limit, txn, data))
    files.pop(0)
    counter += 1

    for filename in files:
        print_status(counter, total)
        arrays.append(firstpass(filename, k, limit, txn))
        counter += 1

    print_status(counter, total)
    print ""

    counter = 0
    arrays[-1] = second_start(arrays[-1], k, txn, data)
    counter += 1

    i = len(arrays)-2
    while i >= 0:
        print_status(counter, total)
        arrays[i] = secondpass(arrays[i], k, txn)
        i-=1
        counter += 1

    print_status(counter, total)
    print "\n"

    return arrays

def make_predictions(train_data, train_labels, test_data, test_labels):
    """
    Helper method for kmer_prediction.run(), should not be used on its own.

    Takes training data and labels, and test data for an svm. If test_lables is
    None returns predictions on test_data, other wise returns a percentage of
    predictions that the svm got correct.
    """
    linear = svm.SVC(kernel='linear')
    output = []

    scaler = MinMaxScaler()
    X = scaler.fit_transform(train_data)
    Z = scaler.transform(test_data)

    try:
        linear.fit(X, train_labels)
        if test_labels:
            ans = linear.score(Z, test_labels)
            return ans
        else:
            return linear.predict(Z)
    except (ValueError, TypeError) as E:
        print E
        return -1

def run(k, limit, num_splits, pos, neg, predict):
    """
    Uses kmer counts of genomes as input to a support vector machine to predict
    presence or absence of a phenotype in a genome.

    Parameters:
        k:          The length of kmer to input
        l:          A lower limit on how many times a kmer needs to be present in a
                    genome in order to be ouput.
        num_splits: How many times to train and test the model. Ignored if
                    predict is not None.
        pos:          Path to a directory containing fasta files for genomes that
                    are positive for a phenotype.
        neg:        Path to a directory containing fasta files for genomes that
                    are negative for a phenotype.
        predict:    Path to a directory containing fasta files for genomes that
                    you want to perdict whether or not they have a phenotype.
                    Can be None, if None the files in pos and neg will be
                    shuffled and split so that 80%% are used to train the model
                    and 20%% to test a model.
    Returns:
        Predict is None:        Percentage of predictions that the model got
                                right. If num_splits greater than 1, this is the
                                average of all runs.
        Predict is not None:    Returns a binary array, where 1 means the
                                genome belongs to the pos group and 0 means the
                                genome belongs to the neg group.
    """

    env = lmdb.open('database', map_size=int(2e9), max_dbs=400)

    data = env.open_db('current', dupsort=False)

    with env.begin(write=True, db=data) as txn:

        if not predict:
            files = pos + neg
        else:
            files = pos + neg + predict

        arrays = setup_data(files, k, limit, txn, data)

        labels=[1 for x in range(len(pos))]+[0 for x in range(len(neg))]

        if not predict:
            sss = ssSplit(n_splits=num_splits, test_size=0.2, random_state=42)

            avg = 0.0

            for indices in sss.split(arrays, labels):
                X = [arrays[x] for x in indices[0]]
                Y = [labels[x] for x in indices[0]]
                Z = [arrays[x] for x in indices[1]]
                ZPrime = [labels[x] for x in indices[1]]

                avg += make_predictions(X, Y, Z, ZPrime)

            return avg/num_splits

        else:
            sss = ssSplit(n_splits = num_splits, test_size = 0.5, random_state=42)

            output = []

            for indices in sss.split(arrays[:(len(pos)+len(neg))], labels):
                X = [arrays[x] for x in indices[0]]
                X.extend([arrays[x] for x in indices[1]])
                Y = [labels[x] for x in indices[0]]
                Y.extend([labels[x] for x in indices[1]])
                Z = arrays[(len(pos)+len(neg)):]

                output.append(make_predictions(X, Y, Z, None))

            return output

        env.close()

def main():
    """
    Handles kmer_prediction.py being run from the command line.
    """
    if len(sys.argv) == 6 or len(sys.argv) == 7:
        k = int(sys.argv[1])
        l = int(sys.argv[2])
        reps = int(sys.argv[3])
        pos = set_up_files(sys.argv[4])
        neg = set_up_files(sys.argv[5])
        if len(sys.argv) == 6:
            output = run(k, l, reps, pos, neg, None)
        else:
            predict = set_up_files(sys.argv[6])
            output = run(k, l, reps, pos, neg, predict)
        print output
    else:
        output = """
        Error: Wrong number of arguments, requires at least 5, at most 6
        First Argument: kmer length
        Second Argument: Minimum kmer count required for a kmer to be output
        Third Argument: Number of times to repeat the training and testing of
                        the model, if greater than 1 returns the average of all
                        runs.
        Fourth Argument: Path to directory containing fasta files for genomes
                         positive for a phenotype.
        Fifth Argument: Path to a directory containing fasta files negative for
                        a phenotype.
        Sixth Argument: (Optional) Path to a directory containing fasta files
                        that you want to predict whether or not they are positive
                        for the phenotype. If supplied, all the files contianed
                        in the fourth and fifth parameter will be used to train
                        the model. If not supplied the files contained in the
                        fourth and fifth argument will be shuffled and 80%% will
                        be used to train the model and the rest will be used to
                        test the model.

        Example: python %s 10 5 5 /home/data/pos/ /home/data/neg/
        Counts kmers with length 10 removing any that appear fewer than 5 times
        then performs the training and testing of the model 5 times using the
        fasta files contained in the positive and negative directories.
        """ % sys.argv[0]
        print output

if __name__ == "__main__":
    main()
