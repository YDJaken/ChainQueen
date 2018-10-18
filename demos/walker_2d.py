# baseline
# *** forward 0.9585404396057129
# *** eval_gradients 2.6700315475463867

# reduced calls to make_matrix2d
# *** forward 0.7795238494873047
# *** eval_gradients 2.3976681232452393

# replaced tf particle mask as precomputed np array
# *** forward 0.4802134037017822
# *** eval_gradients 1.8936614990234375

# avoided goal feature recomputation
# *** forward 0.45941948890686035
# *** eval_gradients 1.8227229118347168

import sys
sys.path.append('..')

import random
import os
import numpy as np
from simulation import Simulation, get_bounding_box_bc
import time
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import tensorflow as tf
import tensorflow.contrib.layers as ly
from vector_math import *
import export 
import IPython

lr = 0.03
gamma = 0.0

sample_density = 20
group_num_particles = sample_density**2
goal_pos = np.array([1.4, 0.4])
goal_range = np.array([0.0, 0.00])
batch_size = 1
actuation_strength = 3

config = 'B'

exp = export.Export('walker_2d')

# Robot B
num_groups = 7
group_offsets = [(0, 0), (0.5, 0), (0, 1), (1, 1), (2, 1), (2, 0), (2.5, 0)]
group_sizes = [(0.5, 1), (0.5, 1), (1, 1), (1, 1), (1, 1), (0.5, 1), (0.5, 1)]
actuations = [0, 1, 5, 6]
fixed_groups = []
head = 3
gravity = (0, -2)

num_particles = group_num_particles * num_groups


def particle_mask(start, end):
  r = np.array(range(0, num_particles))
  return (np.logical_and(start <= r, r < end)).astype(np.float32)[None, :]


def particle_mask_from_group(g):
  return particle_mask(g * group_num_particles, (g + 1) * group_num_particles)


# NN weights
W1 = tf.Variable(
    0.02 * tf.random_normal(shape=(len(actuations), 6 * len(group_sizes))),
    trainable=True)
b1 = tf.Variable([0.0] * len(actuations), trainable=True)


def main(sess):
  t = time.time()

  goal = tf.placeholder(dtype=tf.float32, shape=[batch_size, 2], name='goal')

  # Define your controller here
  def controller(state):
    controller_inputs = []
    goal_feature = (goal - goal_pos) / np.maximum(goal_range, 1e-5)
    for i in range(num_groups):
      mask = particle_mask(i * group_num_particles,
                           (i + 1) * group_num_particles)[:, None, :] * (
                               1.0 / group_num_particles)
      pos = tf.reduce_sum(mask * state.position, axis=2, keepdims=False)
      vel = tf.reduce_sum(mask * state.velocity, axis=2, keepdims=False)
      controller_inputs.append(pos)
      controller_inputs.append(vel)
      controller_inputs.append(goal_feature)
    # Batch, dim
    controller_inputs = tf.concat(controller_inputs, axis=1)
    assert controller_inputs.shape == (batch_size, 6 * num_groups), controller_inputs.shape
    controller_inputs = controller_inputs[:, :, None]
    assert controller_inputs.shape == (batch_size, 6 * num_groups, 1)
    # Batch, 6 * num_groups, 1
    intermediate = tf.matmul(W1[None, :, :] +
                             tf.zeros(shape=[batch_size, 1, 1]), controller_inputs)
    # Batch, #actuations, 1
    assert intermediate.shape == (batch_size, len(actuations), 1)
    assert intermediate.shape[2] == 1
    intermediate = intermediate[:, :, 0]
    # Batch, #actuations
    actuation = tf.tanh(intermediate + b1[None, :]) * actuation_strength
    debug = {'controller_inputs': controller_inputs[:, :, 0], 'actuation': actuation}
    total_actuation = 0
    zeros = tf.zeros(shape=(batch_size, num_particles))
    for i, group in enumerate(actuations):
      act = actuation[:, i:i+1]
      assert len(act.shape) == 2
      mask = particle_mask_from_group(group)
      act = act * mask
      total_actuation = total_actuation + act
    total_actuation = make_matrix2d(zeros, zeros, zeros, total_actuation)
    return total_actuation, debug
  
  res = (80, 40)
  bc = get_bounding_box_bc(res)
  
  sim = Simulation(
      dt=0.005,
      num_particles=num_particles,
      grid_res=res,
      dx=1.0 / res[1],
      gravity=gravity,
      controller=controller,
      batch_size=batch_size,
      bc=bc,
      sess=sess,
      scale=20,
      part_size = 10)
  print("Building time: {:.4f}s".format(time.time() - t))

  final_state = sim.initial_state['debug']['controller_inputs']
  s = head * 6
  
  final_position = final_state[:, s:s+2]
  final_velocity = final_state[:, s + 2: s + 4]
  loss1 = tf.reduce_mean(tf.reduce_sum(-final_position[:, 0]))
  loss2 = tf.reduce_mean(tf.reduce_sum(final_velocity ** 2, axis = 1))

  saver = tf.train.Saver()

  loss = loss1 + gamma * loss2

  initial_positions = [[] for _ in range(batch_size)]
  for b in range(batch_size):
    for i, offset in enumerate(group_offsets):
      for x in range(sample_density):
        for y in range(sample_density):
          scale = 0.2
          u = ((x + 0.5) / sample_density * group_sizes[i][0] + offset[0]
              ) * scale + 0.2
          v = ((y + 0.5) / sample_density * group_sizes[i][1] + offset[1]
              ) * scale + 0.1
          initial_positions[b].append([u, v])
  assert len(initial_positions[0]) == num_particles
  initial_positions = np.array(initial_positions).swapaxes(1, 2)

  sess.run(tf.global_variables_initializer())

  initial_state = sim.get_initial_state(
      position=np.array(initial_positions), youngs_modulus=10)

  trainables = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES)
  sim.set_initial_state(initial_state=initial_state)
  
  tt = time.time()
  sym = sim.gradients_sym(loss, variables=trainables)
  print('sym', time.time() - tt)
  #sim.add_point_visualization(pos=goal, color=(0, 1, 0), radius=3)
  sim.add_vector_visualization(pos=final_position, vector=final_velocity, color=(0, 0, 1), scale=50)
 
  sim.add_point_visualization(pos=final_position, color=(1, 0, 0), radius=3)

  gx, gy = goal_range
  pos_x, pos_y = goal_pos
  goal_train = [np.array(
    [[pos_x + (random.random() - 0.5) * gx,
      pos_y + (random.random() - 0.5) * gy] for _ in range(batch_size)],
    dtype=np.float32) for __ in range(1)]

  vis_id = list(range(batch_size))
  random.shuffle(vis_id)
  grad_ph = [
      tf.placeholder(shape = v.shape, dtype = tf.float32) for v in trainables
  ]
  gradient_descent = [
      v.assign(v - lr * g) for v, g in zip(trainables, grad_ph)
  ]

  # Optimization loop
  for e in range(200):
    t = time.time()
    print('Epoch {:5d}, learning rate {}'.format(e, lr))

    loss_cal = 0.
    print('train...')
    for it, goal_input in enumerate(goal_train):
      tt = time.time()
      memo = sim.run(
          initial_state=initial_state,
          num_steps=800,
          iteration_feed_dict={goal: goal_input},
          loss=loss)
      print('*** forward', time.time() - tt)
      tt = time.time()
      grad = sim.eval_gradients(sym=sym, memo=memo)
      print('*** eval_gradients', time.time() - tt)
      tt = time.time()

      grad_feed_dict = {}
      for gp, g in zip(grad_ph, grad):
        grad_feed_dict[gp] = g
      sess.run(gradient_descent, feed_dict = grad_feed_dict)
      print('gradient_descent', time.time() - tt)
      print('Iter {:5d} time {:.3f} loss {}'.format(
          it, time.time() - t, memo.loss))
      loss_cal = loss_cal + memo.loss
    save_path = saver.save(sess, "./models/walker_2d.ckpt")
    print("Model saved in path: %s" % save_path)
    sim.visualize(memo, batch=random.randrange(batch_size), export=None,
                    show=True, interval=4)
    print('train loss {}'.format(loss_cal / len(goal_train)))
    
if __name__ == '__main__':
  sess_config = tf.ConfigProto(allow_soft_placement=True)
  sess_config.gpu_options.allow_growth = True
  sess_config.gpu_options.per_process_gpu_memory_fraction = 0.4

  with tf.Session(config=sess_config) as sess:
    main(sess=sess)
