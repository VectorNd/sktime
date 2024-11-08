"""Interval-based anomaly detection for time series."""

__all__ = ["IntervalBasedAnomalyDetector"]
__author__ = ["VectorNd"]

import numpy as np
import pandas as pd

from sktime.classification.base import BaseClassifier
from sktime.forecasting.base import BaseForecaster


class IntervalBasedAnomalyDetector(BaseClassifier):
    """Anomaly detector that uses forecasting intervals to detect anomalies.

    Detects anomalies by checking if observations fall outside prediction intervals
    generated by a forecaster.

    Parameters
    ----------
    forecaster : BaseForecaster
        The forecaster to use for generating prediction intervals
    coverage : float, default=0.95
        The coverage of the prediction interval (between 0 and 1)
        Points outside this interval will be marked as anomalies

    Examples
    --------
    >>> from sktime.forecasting.naive import NaiveForecaster
    >>> from sktime.forecasting.anomaly_detector import IntervalBasedAnomalyDetector
    >>> detector = IntervalBasedAnomalyDetector(
    forecaster=NaiveForecaster(),
    coverage=0.95)
    >>> detector.fit(X_train)
    >>> anomalies = detector.predict(X_test)
    >>> probs = detector.predict_proba(X_test)
    """

    def __init__(self, forecaster, coverage=0.95):
        super().__init__()

        if not isinstance(forecaster, BaseForecaster):
            raise ValueError("forecaster must be a BaseForecaster instance")

        if not forecaster.get_tag("capability:pred_int"):
            raise ValueError("forecaster must support prediction intervals")

        if not 0 < coverage < 1:
            raise ValueError("coverage must be between 0 and 1")

        self.forecaster = forecaster
        self.coverage = coverage

    def _fit(self, X, y=None):
        """Fit the anomaly detector.

        Parameters
        ----------
        X : pd.Series or pd.DataFrame
            Training data
        y : None
            Ignored, exists for API consistency

        Returns
        -------
        self : returns a reference to self
        """
        # Fit the forecaster on the training data
        self.forecaster_ = self.forecaster.clone()
        self.forecaster_.fit(X)
        return self

    def _predict(self, X):
        """Predict anomaly labels.

        Parameters
        ----------
        X : pd.Series or pd.DataFrame
            Data to detect anomalies in

        Returns
        -------
        pd.Series
            Returns 1 for anomalies, 0 for normal observations
        """
        # Get prediction intervals
        fh = X.index
        pred_int = self.forecaster_.predict_interval(fh=fh, coverage=self.coverage)

        # Extract lower and upper bounds
        lower = pred_int.xs("lower", level=-1, axis=1)
        upper = pred_int.xs("upper", level=-1, axis=1)

        # Mark points outside the interval as anomalies
        anomalies = (X < lower) | (X > upper)

        # Convert boolean to 0/1
        return anomalies.astype(int)

    def _predict_proba(self, X):
        """Predict anomaly probabilities.

        Parameters
        ----------
        X : pd.Series or pd.DataFrame
            Data to detect anomalies in

        Returns
        -------
        pd.DataFrame
            Returns probability of being an anomaly
        """
        # Get prediction intervals
        fh = X.index
        pred_int = self.forecaster_.predict_interval(fh=fh, coverage=self.coverage)

        # Extract bounds
        lower = pred_int.xs("lower", level=-1, axis=1)
        upper = pred_int.xs("upper", level=-1, axis=1)

        # Calculate z-score-like distance from interval
        center = (upper + lower) / 2
        width = upper - lower
        z_scores = np.abs(X - center) / (width / 2)

        # Convert to probability using sigmoid
        probs = 1 / (1 + np.exp(-(z_scores - 1)))

        return pd.DataFrame(probs, index=X.index)

    @classmethod
    def get_test_params(cls, parameter_set="default"):
        """Return testing parameter settings for the estimator.

        Parameters
        ----------
        parameter_set : str, default="default"
            Name of the set of test parameters to return, for use in tests. If no
            special parameters are defined for a value, will return `"default"` set.

        Returns
        -------
        params : dict
            Parameters to create testing instances of the class
        """
        from sktime.forecasting.naive import NaiveForecaster

        # NaiveForecaster supports prediction intervals and is a simple choice for
        # testing
        params = {"forecaster": NaiveForecaster(strategy="mean"), "coverage": 0.9}
        return params
