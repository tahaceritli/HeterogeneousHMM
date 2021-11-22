"""
Created on Jan 14, 2020
Updated docstrings on Oct 12, 2021

@author: esukei

Parts of the code come from:
    https://github.com/hmmlearn/hmmlearn/blob/master/lib/hmmlearn/tests/test_multinomial_hmm.py
"""


import pytest
import numpy as np

from heterogeneoushmm.multinomial import MultinomialHMM
from hmmlearn.utils import normalize


class TestMultinomialHMM:
    """
    Test based on the example provided on:
        http://en.wikipedia.org/wiki/Hidden_Markov_model
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """
        Initialise a multinomial HMM with some dummy values. 
        """
        self.n_states = 2
        self.n_emissions = 1
        self.n_features = [3]
        self.h = MultinomialHMM(
            self.n_states, self.n_emissions, self.n_features)
        self.h.pi = np.array([0.6, 0.4])
        self.h.A = np.array([[0.7, 0.3], [0.4, 0.6]])
        self.h.B = np.array(
            [[0.1, 0.4, 0.5], [0.6, 0.3, 0.1]]).reshape((1, 2, 3))

    def test_score_samples(self):
        """
        Tests the score_samples method, which returns a list of arrays of shape
        (n_samples, n_states) containing the state-membership probabilities for each
        sample in the observation sequences. So we are testing if the return shape
        is correct and if the posterior probabilities add up to 1.
        """
        idx = np.repeat(np.arange(self.n_states), 10)
        n_samples = len(idx)
        X = [
            np.random.randint(self.n_features[0], size=(n_samples, 1)) for _ in range(4)
        ]

        posteriors = self.h.score_samples(X)
        assert np.any(
            posteriors[i].shape == (n_samples, self.n_states)
            for i in range(len(posteriors))
        )
        assert np.all(
            np.allclose(posteriors[i].sum(axis=1), np.ones(n_samples))
            for i in range(len(posteriors))
        )

    def test_decode_viterbi(self):
        """
        From http://en.wikipedia.org/wiki/Viterbi_algorithm:
        >> This reveals that the observations ['walk', 'shop', 'clean']
        were most likely generated by states ['Sunny', 'Rainy', 'Rainy'],
        with probability 0.01344. 
        """
        X = [[[0], [1], [2]]]
        log_likelihood, state_sequence = self.h.decode(X, algorithm="viterbi")
        assert round(np.exp(log_likelihood), 5) == 0.01344
        assert np.allclose(state_sequence, [1, 0, 0])

    def test_decode_map(self):
        """
        From http://en.wikipedia.org/wiki/Viterbi_algorithm:
        >> This reveals that the observations ['walk', 'shop', 'clean']
        were most likely generated by states ['Sunny', 'Rainy', 'Rainy']
        """
        X = [[[0], [1], [2]]]
        _, state_sequence = self.h.decode(X, algorithm="map")
        assert np.allclose(state_sequence, [1, 0, 0])

    def test_sample(self, n_samples=1000, n_sequences=5):
        """
        Test if the sampling method generates the correct number of 
        sequences with corrent number of samples.

        :param n_samples: number of samples to generate for each sequence, defaults to 1000
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 5
        :type n_sequences: int, optional
        """
        X, state_sequences = self.h.sample(
            n_sequences=n_sequences, n_samples=n_samples, return_states=True)
        assert np.all(X[i].ndim == 2 for i in range(n_sequences))
        assert np.all(
            len(X[i]) == len(state_sequences[i]) == n_samples
            for i in range(n_sequences)
        )
        for j in range(self.n_emissions):
            assert np.all(
                len(np.unique(X[i][:, j])) == self.n_features[j]
                for i in range(n_sequences)
            )

    def test_train(self, n_samples=100, n_sequences=30, tr_params="ste"):
        """
        Test if the training algorithm works correctly (if the log-likelihood increases).

        :param n_samples: number of samples to generate for each sequence, defaults to 100
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 30
        :type n_sequences: int, optional
        :param tr_params: which model parameters to train, defaults to "ste"
        :type tr_params: str, optional
        """
        h = self.h
        h.tr_params = tr_params
        # Generate observation sequences
        X = self.h.sample(n_sequences=n_sequences, n_samples=n_samples)

        # Mess up the parameters and see if we can re-learn them.
        _, log_likelihoods = h._train(
            X, n_iter=100, conv_thresh=0.01, return_log_likelihoods=True
        )

        # we consider learning if the log_likelihood increases
        assert np.all(np.round(np.diff(log_likelihoods), 10) >= 0)

    def test_train_without_init(self, n_samples=100, n_sequences=30, tr_params="ste"):
        """
        Test if the training algorithm raises an error if it's run without initialising 
        the variables first.

        :param n_samples: number of samples to generate for each sequence, defaults to 100
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 30
        :type n_sequences: int, optional
        :param tr_params: which model parameters to train, defaults to "ste"
        :type tr_params: str, optional
        """
        h = MultinomialHMM(
            self.n_states, self.n_emissions, self.n_features, tr_params=tr_params
        )

        # Generate observation sequences
        X = self.h.sample(n_sequences=n_sequences, n_samples=n_samples)

        with pytest.raises(AttributeError):
            h, _ = h._train(
                X, n_iter=100, conv_thresh=0.01, return_log_likelihoods=True, no_init=True, n_processes=2
            )

    def test_only_emission_train(self, n_samples=100, n_sequences=30, tr_params="e"):
        """
        Test if the emission probabilities can be re-learnt. 

        :param n_samples: number of samples to generate for each sequence, defaults to 100
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 30
        :type n_sequences: int, optional
        :param tr_params: which model parameters to train, defaults to "e"
        :type tr_params: str, optional
        """
        h = self.h
        h.tr_params = tr_params
        # Generate observation sequences
        X = self.h.sample(n_sequences=n_sequences, n_samples=n_samples)

        # Mess up the emission probabilities and see if we can re-learn them.
        h.B = np.asarray(
            [
                np.random.random((self.n_states, self.n_features[i]))
                for i in range(self.n_emissions)
            ]
        )
        for i in range(self.n_emissions):
            normalize(h.B[i], axis=1)

        h, log_likelihoods = h._train(
            X, n_iter=100, conv_thresh=0.01, return_log_likelihoods=True, no_init=True
        )

        # we consider learning if the log_likelihood increases
        assert np.all(np.round(np.diff(log_likelihoods), 10) >= 0)

    def test_non_trainable_emission(self, n_samples=100, n_sequences=30, tr_params="ste"):
        """
        Test if the non-training of the last emission probabilities works.

        :param n_samples: number of samples to generate for each sequence, defaults to 100
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 30
        :type n_sequences: int, optional
        :param tr_params: which model parameters to train, defaults to "e"
        :type tr_params: str, optional
        """
        h = MultinomialHMM(
            self.n_states,
            self.n_emissions,
            self.n_features,
            nr_no_train_de=1,
            tr_params=tr_params,
        )

        # Generate observation sequences
        X = self.h.sample(
            n_sequences=n_sequences, n_samples=n_samples)

        # Set up the emission probabilities and see if we can re-learn them.
        B_fix = np.asarray(
            [np.eye(self.n_states, self.n_features[i])
             for i in range(self.n_emissions)]
        )

        h.B = B_fix

        with pytest.raises(AttributeError):
            h, _ = h._train(
                X, n_iter=10, conv_thresh=0.01, return_log_likelihoods=True, no_init=False
            )

            # we want that the emissions haven't changed
            assert np.allclose(B_fix, h.B)

    def test_non_trainable_emission_not_set(
        self, n_samples=100, n_sequences=30, tr_params="ste"
    ):
        """
        Test whether an error is thrown if a non-trainaible emission probabilities are
        not initialised. 

        :param n_samples: number of samples to generate for each sequence, defaults to 100
        :type n_samples: int, optional
        :param n_sequences: number of sequences to generate, defaults to 30
        :type n_sequences: int, optional
        :param tr_params: which model parameters to train, defaults to "e"
        :type tr_params: str, optional
        """
        h = MultinomialHMM(
            self.n_states,
            self.n_emissions,
            self.n_features,
            nr_no_train_de=1,
            tr_params=tr_params,
        )

        # Generate observation sequences
        X = self.h.sample(n_sequences=n_sequences, n_samples=n_samples)

        with pytest.raises(AttributeError):
            h, _ = h._train(
                X, n_iter=100, conv_thresh=0.01, return_log_likelihoods=True, no_init=True
            )
