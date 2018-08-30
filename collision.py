import random
import time
from simulation import Simulation, get_bounding_box_bc
from time_integration import UpdatedSimulationState
import tensorflow as tf
import numpy as np
from IPython import embed

batch_size = 1
gravity = (0, 0)
N = 10
group_particles = N * N * 2
num_particles = group_particles * 2
steps = 100
dt = 1e-2
goal_range = 0.15
res = (30, 30)
bc = get_bounding_box_bc(res)

lr = 1e-2

def main(sess):
  
  goal = tf.placeholder(dtype=tf.float32, shape=[batch_size, 2], name='goal')

  sim = Simulation(
      dt=dt,
      num_particles=num_particles,
      grid_res=res,
      bc=bc,
      gravity=gravity,
      sess=sess)
  position = np.zeros(shape=(batch_size, num_particles, 2))
  youngs_modulus = np.zeros(shape=(batch_size, num_particles, 1))

  velocity_ph = tf.Variable([0.3, 0.05], trainable = True)
  velocity_1 = velocity_ph[None, None, :] + tf.zeros(
      shape=[batch_size, group_particles, 2], dtype=tf.float32)
  velocity_2 = tf.zeros(shape=[batch_size, group_particles, 2], dtype=tf.float32)
  velocity = tf.concat([velocity_1, velocity_2], axis = 1)

  for b in range(batch_size):
    for i in range(group_particles):
      x, y = 0, 0
      while (x - 0.5) ** 2 + (y - 0.5) ** 2 > 0.25:
        x, y = random.random(), random.random()
      position[b, i] = ((x * 2 + 3) / 30,
                        (y * 2 + 12.75) / 30)

    for i in range(group_particles):
      x, y = 0, 0
      while (x - 0.5) ** 2 + (y - 0.5) ** 2 > 0.25:
        x, y = random.random(), random.random()
      position[b, i + group_particles] = ((x * 2 + 10) / 30,
                                          (y * 2 + 12.75) / 30)

  sess.run(tf.global_variables_initializer())

  initial_state = sim.get_initial_state(
      position=position, velocity=velocity)

  final_position = sim.initial_state.center_of_mass(group_particles, None)
  loss = tf.reduce_sum((final_position - goal) ** 2) ** 0.5
  # loss = tf.reduce_sum(tf.abs(final_position - goal))
  sim.add_point_visualization(pos = final_position, color = (1, 0, 0), radius = 3)
  sim.add_point_visualization(pos = goal, color = (0, 1, 0), radius = 3)

  trainables = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES)
  sim.set_initial_state(initial_state = initial_state)

  sym = sim.gradients_sym(loss, variables = trainables)

  goal_input = np.array(
          [[0.7, 0.4]],
    dtype=np.float32)

  for i in range(1000000):
    # if i > 10:
    #     lr = 1e-1
    # elif i > 20:
    #     lr = 1e-2
    t = time.time()
    memo = sim.run(
        initial_state = initial_state, 
        num_steps = steps,
        iteration_feed_dict = {goal: goal_input},
        loss = loss)
    grad = sim.eval_gradients(sym, memo)
    gradient_descent = [
        v.assign(v - lr * g) for v, g in zip(trainables, grad)
    ]
    sess.run(gradient_descent)
    print('iter {:5d} time {:.3f} loss {:.4f}'.format(
        i, time.time() - t, memo.loss))
    if i % 5 == 0: # True: # memo.loss < 0.01: 
      sim.visualize(memo)
    
if __name__ == '__main__':
  sess_config = tf.ConfigProto(allow_soft_placement=True)
  sess_config.gpu_options.allow_growth = True
  sess_config.gpu_options.per_process_gpu_memory_fraction = 0.4

  with tf.Session(config=sess_config) as sess:
    main(sess=sess)