import numpy as np
from trulens.nn.attribution import InternalInfluence
from trulens.nn.backend import get_backend
from trulens.nn.distributions import GaussianDoi, LinearDoi, PointDoi
from trulens.nn.quantities import LambdaQoI
from trulens.nn.slices import Cut, InputCut, OutputCut
from trulens.utils.typing import ModelInputs


class DoiTestBase(object):

    def setUp(self):
        # Create an example tensor to use for the tests.
        self.B = get_backend()
        self.z = self.B.as_tensor(np.array([[1., 2., 3.], [0., -1., -2.]]))


        # Weights of a simple neural network for testing optional model_input args.
        self.l1_coeff = 1
        self.l1_exp = 2
        self.l2_coeff = 3
        self.l2_exp = 4
        # output = l2_coeff * (l1_coeff * (input ^ l1_exp)) ^ l2_exp

        self.consts = np.array([1.0, 2.0, 5.0])

    # Tests for PointDoI.

    def test_point(self):

        res = PointDoi()(self.z)

        self.assertEqual(len(res), 1, 'PointDoi should return a single point')

        self.assertTrue(
            np.array_equal(self.B.as_array(res[0]), self.B.as_array(self.z)),
            'Value of point should not change')

    # Tests for LinearDoI.

    def test_linear(self):

        doi = LinearDoi(
            baseline=np.ones(self.B.int_shape(self.z)), resolution=21)
        res = doi(self.z)

        self.assertEqual(
            len(res), 21, 'LinearDoi should return `resolution` points')

        self.assertTrue(
            np.array_equal(self.B.as_array(res[0]), self.B.as_array(self.z)),
            'First point should be the original point')

        self.assertTrue(
            np.all(self.B.as_array(res[-1]) == 1.),
            'Last point should be baseline')

        self.assertTrue(
            np.allclose(
                self.B.as_array(res[-2]),
                np.array([[1., 1.05, 1.1], [0.95, 0.9, 0.85]])),
            'Intermediate points should interpolate from baseline')

    def test_linear_point(self):
        doi = LinearDoi(resolution=1)
        res = doi(self.z)

        self.assertEqual(
            len(res), 1, 'LinearDoi should return `resolution` points')

        self.assertTrue(
            np.array_equal(self.B.as_array(res[0]), self.B.as_array(self.z)),
            'When `resolution` is 1, should be the same as PointDoi')

    def test_linear_default_baseline(self):
        doi = LinearDoi(baseline=None, resolution=10)
        res = doi(self.z)

        self.assertTrue(
            np.all(self.B.as_array(res[-1]) == 0.),
            'Default baseline should be zeros')

    def test_linear_from_computed_nearby_baseline(self):
        # Baseline for cut value is a function of value at that cut.

        doi = LinearDoi(lambda z: z + 42)

        res = doi(self.z)

        self.assertTrue(
            np.all(self.B.as_array(res[0]) == self.B.as_array(self.z)),
            'Starting point of linear baseline should be base cut value.')

        self.assertTrue(
            np.all(self.B.as_array(res[-1]) == self.B.as_array(self.z + 42)),
            'End point of linear baseline should be computed cut value.')

    def test_model_inputs_for_baseline(self):
        # Test the model_inptus optional argument for callable baseline.
        pass

    def test_model_inputs_for_doi(self):
        # Test the model_inputs optional argument for doi's.

        class DoiOnInput(PointDoi):
            def __call__(self, z, *, model_inputs: ModelInputs):
                # ignore value at cut, return model input instead
                return [model_inputs.args[0]]

        class DoiOnCut(PointDoi):
            def __call__(self, z, *, model_inputs: ModelInputs):
                return [z]

        doi1 = DoiOnCut(cut=Cut(1))   

        doi2 = DoiOnInput(cut=Cut(1))
        # will return values at Cut(0) despite defining values for Cut(1)

        infl1 = InternalInfluence(
            self.model,
            (Cut(1), OutputCut()),
            LambdaQoI(lambda out: out),
            doi1,
            multiply_activation=False)

        res1 = infl1.attributions(self.consts)

        l0 = self.consts
        l1 = self.l1_coeff * (l0 ** self.l1_exp)
        l2 = self.l2_coeff * (l1 ** self.l2_exp)

        # d l2 / d l1 evaluated at l1
        expect1 = self.l2_coeff * self.l2_exp * (l1 ** (self.l2_exp-1.0))

        self.assertTrue(np.allclose(res1, expect1))
        
        infl2 = InternalInfluence(
            self.model,
            (Cut(1), OutputCut()),
            LambdaQoI(lambda out: out),
            doi2,
            multiply_activation=False)

        res2 = infl2.attributions(self.consts)

        # d l2 / d l1 evaluated at l0 (due to doi2 returning model inputs = l0)
        expect2 = self.l2_coeff * self.l2_exp * (l0 ** (self.l2_exp-1.0))

        self.assertTrue(np.allclose(res2, expect2))

    # Tests for GaussianDoI.

    def test_gaussian(self):

        doi = GaussianDoi(var=1., resolution=10)
        res = doi(self.z)

        self.assertEqual(
            len(res), 10, 'GaussianDoi should return `resolution` points')

        self.assertEqual(self.B.int_shape(res[0]), self.B.int_shape(self.z))

    def test_gaussian_non_tensor(self):

        doi = GaussianDoi(var=1., resolution=10)
        res = doi(self.B.as_array(self.z))

        self.assertEqual(
            len(res), 10, 'GaussianDoi should return `resolution` points')

        self.assertEqual(res[0].shape, self.B.int_shape(self.z))
