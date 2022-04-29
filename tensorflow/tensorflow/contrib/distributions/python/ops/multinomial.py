# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""The Multinomial distribution class."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.contrib.distributions.python.ops import distribution
from tensorflow.contrib.distributions.python.ops import distribution_util
from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import check_ops
from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import random_ops


__all__ = [
    "Multinomial",
]


_multinomial_sample_note = """For each batch of counts, `value = [n_0, ...
,n_{k-1}]`, `P[value]` is the probability that after sampling `self.total_count`
draws from this Multinomial distribution, the number of draws falling in class
`j` is `n_j`. Since this definition is [exchangeable](
https://en.wikipedia.org/wiki/Exchangeable_random_variables); different
sequences have the same counts so the probability includes a combinatorial
coefficient.

Note: `value` must be a non-negative tensor with dtype `self.dtype`, have no
fractional components, and such that
`tf.reduce_sum(value, -1) = self.total_count`. Its shape must be broadcastable
with `self.probs` and `self.total_count`."""


class Multinomial(distribution.Distribution):
  """Multinomial distribution.

  This Multinomial distribution is parameterized by `probs`, a (batch of)
  length-`k` `prob` (probability) vectors (`k > 1`) such that
  `tf.reduce_sum(probs, -1) = 1`, and a `total_count` number of trials, i.e.,
  the number of trials per draw from the Multinomial. It is defined over a
  (batch of) length-`k` vector `counts` such that
  `tf.reduce_sum(counts, -1) = total_count`. The Multinomial is identically the
  Binomial distribution when `k = 2`.

  #### Mathematical Details

  The Multinomial is a distribution over `k`-class counts, i.e., a length-`k`
  vector of non-negative integer `counts = n = [n_0, ..., n_{k-1}]`.

  The probability mass function (pmf) is,

  ```none
  pmf(n; pi, N) = prod_j (pi_j)**n_j / Z
  Z = (prod_j n_j!) / N!
  ```

  where:
  * `probs = pi = [pi_0, ..., pi_{k-1}]`, `pi_j > 0`, `sum_j pi_j = 1`,
  * `total_count = N`, `N` a positive integer,
  * `Z` is the normalization constant, and,
  * `N!` denotes `N` factorial.

  Distribution parameters are automatically broadcast in all functions; see
  examples for details.

  #### Examples

  Create a 3-class distribution, with the 3rd class is most likely to be drawn,
  using logits.

  ```python
  logits = [-50., -43, 0]
  dist = Multinomial(total_count=4., logits=logits)
  ```

  Create a 3-class distribution, with the 3rd class is most likely to be drawn.

  ```python
  p = [.2, .3, .5]
  dist = Multinomial(total_count=4., probs=p)
  ```

  The distribution functions can be evaluated on counts.

  ```python
  # counts same shape as p.
  counts = [1., 0, 3]
  dist.prob(counts)  # Shape []

  # p will be broadcast to [[.2, .3, .5], [.2, .3, .5]] to match counts.
  counts = [[1., 2, 1], [2, 2, 0]]
  dist.prob(counts)  # Shape [2]

  # p will be broadcast to shape [5, 7, 3] to match counts.
  counts = [[...]]  # Shape [5, 7, 3]
  dist.prob(counts)  # Shape [5, 7]
  ```

  Create a 2-batch of 3-class distributions.

  ```python
  p = [[.1, .2, .7], [.3, .3, .4]]  # Shape [2, 3]
  dist = Multinomial(total_count=[4., 5], probs=p)

  counts = [[2., 1, 1], [3, 1, 1]]
  dist.prob(counts)  # Shape [2]
  ```
  """

  def __init__(self,
               total_count,
               logits=None,
               probs=None,
               validate_args=False,
               allow_nan_stats=True,
               name="Multinomial"):
    """Initialize a batch of Multinomial distributions.

    Args:
      total_count: Non-negative floating point tensor with shape broadcastable
        to `[N1,..., Nm]` with `m >= 0`. Defines this as a batch of
        `N1 x ... x Nm` different Multinomial distributions. Its components
        should be equal to integer values.
      logits: Floating point tensor representing the log-odds of a
        positive event with shape broadcastable to `[N1,..., Nm, k], m >= 0`,
        and the same dtype as `total_count`. Defines this as a batch of
        `N1 x ... x Nm` different `k` class Multinomial distributions. Only one
        of `logits` or `probs` should be passed in.
      probs: Positive floating point tensor with shape broadcastable to
        `[N1,..., Nm, k]` `m >= 0` and same dtype as `total_count`. Defines
        this as a batch of `N1 x ... x Nm` different `k` class Multinomial
        distributions. `probs`'s components in the last portion of its shape
        should sum to `1`. Only one of `logits` or `probs` should be passed in.
      validate_args: Python `bool`, default `False`. When `True` distribution
        parameters are checked for validity despite possibly degrading runtime
        performance. When `False` invalid inputs may silently render incorrect
        outputs.
      allow_nan_stats: Python `bool`, default `True`. When `True`, statistics
        (e.g., mean, mode, variance) use the value "`NaN`" to indicate the
        result is undefined. When `False`, an exception is raised if one or
        more of the statistic's batch members are undefined.
      name: Python `str` name prefixed to Ops created by this class.
    """
    parameters = locals()
    with ops.name_scope(name, values=[total_count, logits, probs]):
      self._total_count = self._maybe_assert_valid_total_count(
          ops.convert_to_tensor(total_count, name="total_count"),
          validate_args)
      self._logits, self._probs = distribution_util.get_logits_and_probs(
          logits=logits,
          probs=probs,
          multidimensional=True,
          validate_args=validate_args,
          name=name)
      self._mean_val = self._total_count[..., array_ops.newaxis] * self._probs
    super(Multinomial, self).__init__(
        dtype=self._probs.dtype,
        reparameterization_type=distribution.NOT_REPARAMETERIZED,
        validate_args=validate_args,
        allow_nan_stats=allow_nan_stats,
        parameters=parameters,
        graph_parents=[self._total_count,
                       self._logits,
                       self._probs],
        name=name)

  @property
  def total_count(self):
    """Number of trials used to construct a sample."""
    return self._total_count

  @property
  def logits(self):
    """Vector of coordinatewise logits."""
    return self._logits

  @property
  def probs(self):
    """Probability of of drawing a `1` in that coordinate."""
    return self._probs

  def _batch_shape_tensor(self):
    return array_ops.shape(self._mean_val)[:-1]

  def _batch_shape(self):
    return self._mean_val.get_shape().with_rank_at_least(1)[:-1]

  def _event_shape_tensor(self):
    return array_ops.shape(self._mean_val)[-1:]

  def _event_shape(self):
    return self._mean_val.get_shape().with_rank_at_least(1)[-1:]

  def _sample_n(self, n, seed=None):
    n_draws = math_ops.cast(self.total_count, dtype=dtypes.int32)
    if self.total_count.get_shape().ndims is not None:
      if self.total_count.get_shape().ndims != 0:
        raise NotImplementedError(
            "Sample only supported for scalar number of draws.")
    elif self.validate_args:
      is_scalar = check_ops.assert_rank(
          n_draws, 0,
          message="Sample only supported for scalar number of draws.")
      n_draws = control_flow_ops.with_dependencies([is_scalar], n_draws)
    k = self.event_shape_tensor()[0]
    # Flatten batch dims so logits has shape [B, k],
    # where B = reduce_prod(self.batch_shape_tensor()).
    draws = random_ops.multinomial(
        logits=array_ops.reshape(self.logits, [-1, k]),
        num_samples=n * n_draws,
        seed=seed)
    draws = array_ops.reshape(draws, shape=[-1, n, n_draws])
    x = math_ops.reduce_sum(array_ops.one_hot(draws, depth=k),
                            axis=-2)  # shape: [B, n, k]
    x = array_ops.transpose(x, perm=[1, 0, 2])
    final_shape = array_ops.concat([[n], self.batch_shape_tensor(), [k]], 0)
    return array_ops.reshape(x, final_shape)

  @distribution_util.AppendDocstring(_multinomial_sample_note)
  def _log_prob(self, counts):
    return self._log_unnormalized_prob(counts) - self._log_normalization(counts)

  @distribution_util.AppendDocstring(_multinomial_sample_note)
  def _prob(self, counts):
    return math_ops.exp(self._log_prob(counts))

  def _log_unnormalized_prob(self, counts):
    counts = self._maybe_assert_valid_sample(counts)
    return math_ops.reduce_sum(counts * math_ops.log(self.probs), -1)

  def _log_normalization(self, counts):
    counts = self._maybe_assert_valid_sample(counts)
    return -distribution_util.log_combinations(self.total_count, counts)

  def _mean(self):
    return array_ops.identity(self._mean_val)

  def _covariance(self):
    p = self.probs * array_ops.ones_like(
        self.total_count)[..., array_ops.newaxis]
    return array_ops.matrix_set_diag(
        -math_ops.matmul(self._mean_val[..., array_ops.newaxis],
                         p[..., array_ops.newaxis, :]),  # outer product
        self._variance())

  def _variance(self):
    p = self.probs * array_ops.ones_like(
        self.total_count)[..., array_ops.newaxis]
    return self._mean_val - self._mean_val * p

  def _maybe_assert_valid_total_count(self, total_count, validate_args):
    if not validate_args:
      return total_count
    return control_flow_ops.with_dependencies([
        check_ops.assert_non_negative(
            total_count,
            message="total_count must be non-negative."),
        distribution_util.assert_integer_form(
            total_count,
            message="total_count cannot contain fractional values."),
    ], total_count)

  def _maybe_assert_valid_sample(self, counts):
    """Check counts for proper shape, values, then return tensor version."""
    if not self.validate_args:
      return counts

    counts = distribution_util.embed_check_nonnegative_discrete(
        counts, check_integer=True)
    return control_flow_ops.with_dependencies([
        check_ops.assert_equal(
            self.total_count, math_ops.reduce_sum(counts, -1),
            message="counts must sum to `self.total_count`"),
    ], counts)
