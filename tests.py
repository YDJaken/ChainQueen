import unittest
from simulation import Simulation
from time_integration import SimulationState, InitialSimulationState, UpdatedSimulationState
import tensorflow as tf
import numpy as np

sess = tf.Session()

class TestSimulator(unittest.TestCase):

  def test_acceleration(self):
    pass

  def test_free_fall(self):
    pass

  def test_translation(self):
    # Zero gravity, 1-batched, translating block
    num_particles = 100
    sim = Simulation(grid_res=(30, 30), num_particles=num_particles)
    initial = sim.initial_state
    next_state = UpdatedSimulationState(sim, initial)
    position = np.array(shape=(1, num_particles, 2))
    for i in range(10):
      for j in range(10):
        position[i * 10 + j] = (i * 0.5 + 10, j * 0.5 + 10)
    sim.get_initial_state(position=position)
    sess.eval(next_state, initial)

  def test_translation_batched(self):
    pass

if __name__ == '__main__':
  unittest.main()