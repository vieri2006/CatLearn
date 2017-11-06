"""Script to test data generation functions."""
from __future__ import print_function
from __future__ import absolute_import

import os
import numpy as np
from random import random

from ase.ga.data import DataConnection

from atoml.utilities.data_setup import get_unique, get_train
from atoml.fingerprint.setup import return_fpv
from atoml.fingerprint import ParticleFingerprintGenerator
from atoml.fingerprint import StandardFingerprintGenerator
from atoml.fingerprint.neighbor_matrix import neighbor_features
from atoml.utilities import DescriptorDatabase

wkdir = os.getcwd()


def setup_test():
    # Connect database generated by a GA search.
    gadb = DataConnection('{}/data/gadb.db'.format(wkdir))

    # Get all relaxed candidates from the db file.
    print('Getting candidates from the database')
    all_cand = gadb.get_all_relaxed_candidates(use_extinct=False)

    # Setup the test and training datasets.
    testset = get_unique(atoms=all_cand, size=10, key='raw_score')
    assert len(testset['atoms']) == 10
    assert len(testset['taken']) == 10

    trainset = get_train(atoms=all_cand, size=50, taken=testset['taken'],
                         key='raw_score')
    assert len(trainset['atoms']) == 50
    assert len(trainset['target']) == 50

    # Clear out some old saved data.
    for i in trainset['atoms']:
        del i.info['data']['nnmat']

    # Initiate the fingerprint generators with relevant input variables.
    print('Getting the fingerprints')
    pfpv = ParticleFingerprintGenerator(atom_numbers=[78, 79], max_bonds=13,
                                        get_nl=False, dx=0.2, cell_size=50.,
                                        nbin=4)
    sfpv = StandardFingerprintGenerator(atom_types=[78, 79])

    data = return_fpv(trainset['atoms'], [pfpv.nearestneighbour_fpv],
                      use_prior=False)
    n, d = np.shape(data)
    assert n == 50, d == 4

    train_fp = return_fpv(trainset['atoms'], [pfpv.bond_count_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 52

    train_fp = return_fpv(trainset['atoms'], [pfpv.distribution_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 8

    train_fp = return_fpv(trainset['atoms'], [pfpv.connections_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 26

    train_fp = return_fpv(trainset['atoms'], [pfpv.rdf_fpv], use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 20

    # Start testing the standard fingerprint vector generators.
    train_fp = return_fpv(trainset['atoms'], [sfpv.mass_fpv], use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 1

    train_fp = return_fpv(trainset['atoms'], [sfpv.composition_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 2

    train_fp = return_fpv(trainset['atoms'], [sfpv.eigenspectrum_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 147

    train_fp = return_fpv(trainset['atoms'], [sfpv.distance_fpv],
                          use_prior=False)
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 2

    train_fp = return_fpv(trainset['atoms'], [pfpv.nearestneighbour_fpv,
                                              sfpv.mass_fpv,
                                              sfpv.composition_fpv])
    n, d = np.shape(train_fp)
    data = np.concatenate((data, train_fp), axis=1)
    assert n == 50, d == 7

    # Do basic check for atomic porperties.
    no_prop = []
    an_prop = []
    for atoms in trainset['atoms']:
        no_prop.append(neighbor_features(atoms=atoms))
        an_prop.append(neighbor_features(atoms=atoms,
                                         property=['atomic_number']))
    data = np.concatenate((data, no_prop), axis=1)
    data = np.concatenate((data, an_prop), axis=1)
    assert np.shape(no_prop) == (50, 15) and np.shape(an_prop) == (50, 30)

    # Define variables for database to store system descriptors.
    db_name = '/fpv_store.sqlite'
    descriptors = ['f' + str(i) for i in range(np.shape(data)[1])]
    targets = ['Energy']
    names = descriptors + targets

    # Set up the database to save system descriptors.
    dd = DescriptorDatabase(db_name=wkdir+db_name, table='FingerVector')
    dd.create_db(names=names)

    # Put data in correct format to be inserted into database.
    print('Generate the database')
    new_data = []
    for i, a in zip(data, all_cand):
        d = []
        d.append(a.info['unique_id'])
        for j in i:
            d.append(j)
        d.append(a.info['key_value_pairs']['raw_score'])
        new_data.append(d)

    # Fill the database with the data.
    dd.fill_db(descriptor_names=names, data=new_data)

    # Test out the database functions.
    train_fingerprint = dd.query_db(names=descriptors)
    train_target = dd.query_db(names=targets)
    print('\nfeature data for candidates:\n', train_fingerprint,
          '\ntarget data for candidates:\n', train_target)

    cand_data = dd.query_db(unique_id='7a216711c2eae02decc04da588c9e592')
    print('\ndata for random candidate:\n', cand_data)

    all_id = dd.query_db(names=['uuid'])
    dd.create_column(new_column=['random'])
    for i in all_id:
        dd.update_descriptor(descriptor='random', new_data=random(),
                             unique_id=i[0])
    print('\nretrieve random vars:\n', dd.query_db(names=['random']))

    print('\nretrieved column names:\n', dd.get_column_names())
