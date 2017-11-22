import sys

import numpy as np
from sklearn.model_selection import KFold


# simple splitters ----------------------------------------------------------

class Splitter(object):
    "Base class used by simple splitters with data as only input"

    def __init__(self, data):
        self.data = data
        self.reset()

    def reset(self):
        self.count = 0

    def __iter__(self):
        return self

    def next(self):
        if self.count > 0:
            raise StopIteration
        tup = self.next_split()
        self.count += 1
        return tup

    # py3 compat
    def __next__(self):
        return self.next()

    def __repr__(self):
        msg = ""
        splitter = self.__class__.__name__
        msg += splitter + "(data)"
        return msg


class TournamentSplitter(Splitter):
    "Single split of data into train, tournament"

    def next_split(self):
        return self.data['train'], self.data['tournament']


class ValidationSplitter(Splitter):
    "Single split of data into train, validation"

    def next_split(self):
        return self.data['train'], self.data['validation']


class CheatSplitter(Splitter):
    "Single split of data into train+validation, tournament"

    def next_split(self):
        dfit = self.data.region_isin(['train', 'validation'])
        dpredict = self.data['validation']
        return dfit, dpredict


# complicated splitters -----------------------------------------------------

class Splitter2(Splitter):
    "Base class used by splitters with input besides data"

    def __repr__(self):
        msg = ""
        splitter = self.__class__.__name__
        msg += splitter + "(data, "
        for name, value in self.p.items():
            if name != 'data':
                msg += name + "=" + str(value) + ", "
        msg = msg[:-2]
        msg += ")"
        return msg


class SplitSplitter(Splitter2):
    "Single fit-predict split of data"

    def __init__(self, data, fit_fraction, seed=0, train_only=True):
        self.p = {'data': data,
                  'fit_fraction': fit_fraction,
                  'seed': seed,
                  'train_only': train_only}
        self.reset()

    def next_split(self):
        data = self.p['data']
        if self.p['train_only']:
            data = data['train']
        eras = data.unique_era()
        rs = np.random.RandomState(self.p['seed'])
        rs.shuffle(eras)
        nfit = int(self.p['fit_fraction'] * eras.size + 0.5)
        data_fit = data.era_isin(eras[:nfit])
        data_predict = data.era_isin(eras[nfit:])
        return data_fit, data_predict


class CVSplitter(Splitter2):
    "K-fold cross validation fit-predict splits across train eras"

    def __init__(self, data, kfold=5, seed=0, train_only=True):
        self.p = {'data': data,
                  'kfold': kfold,
                  'seed': seed,
                  'train_only': train_only}
        self.eras = None
        self.cv = None
        self.reset()

    def next(self):
        if self.count >= self.p['kfold']:
            raise StopIteration
        data = self.p['data']
        if self.count == 0:
            if self.p['train_only']:
                data = data['train']
            self.eras = data.unique_era()
            cv = KFold(n_splits=self.p['kfold'], random_state=self.p['seed'],
                       shuffle=True)
            self.cv = cv.split(self.eras)
        if sys.version_info[0] == 2:
            fit_index, predict_index = self.cv.next()
        else:
            fit_index, predict_index = self.cv.__next__()
        era_fit = [self.eras[i] for i in fit_index]
        era_predict = [self.eras[i] for i in predict_index]
        dfit = data.era_isin(era_fit)
        dpredict = data.era_isin(era_predict)
        self.count += 1
        return dfit, dpredict


class RollSplitter(Splitter2):
    "Roll forward through consecutive eras to generate fit, train splits"

    def __init__(self, data, fit_window, predict_window, step,
                 train_only=True):
        self.p = {'data': data,
                  'fit_window': fit_window,
                  'predict_window': predict_window,
                  'step': step,
                  'train_only': train_only}
        self.eras = None
        self.cv = None
        self.reset()

    def next(self):
        data = self.p['data']
        if self.count == 0:
            if self.p['train_only']:
                data = data['train']
            self.eras = data.unique_era()
        f_idx1 = self.count * self.p['step']
        f_idx2 = f_idx1 + self.p['fit_window']
        p_idx1 = f_idx2
        p_idx2 = p_idx1 + self.p['predict_window']
        nera = self.eras.size
        if p_idx2 > nera:
            raise StopIteration
        era_fit = []
        era_pre = []
        for i in range(nera):
            n_ifs = 0
            if i >= f_idx1 and i < f_idx2:
                era_fit.append(self.eras[i])
                n_ifs += 1
            if i >= p_idx1 and i < p_idx2:
                era_pre.append(self.eras[i])
                n_ifs += 1
            if n_ifs > 1:
                raise RuntimeError("You found a RollSplitter bug!")
        dfit = data.era_isin(era_fit)
        dpre = data.era_isin(era_pre)
        self.count += 1
        return dfit, dpre
