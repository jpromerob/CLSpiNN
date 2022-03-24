import spynnaker8 as p
from pyNN.space import Grid2D
from spinn_front_end_common.utilities.database import DatabaseConnection
import socket
import pdb
import math
import collections

# import cv2

import datetime
import time
import numpy as np
from random import randint, random
from struct import pack
from time import sleep
from threading import Thread

import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams['toolbar'] = 'None' 
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import multiprocessing 


global end_of_sim, input_q, output_q, spike_q

for  i in [8,16,32,64,128,256,512,640]:
    WIDTH = i
    HEIGHT = int(i*3/4)
    SUB_HEIGHT = 2**math.ceil(math.log(math.ceil(math.log(max(2,int(HEIGHT*WIDTH/256)),2)),2))
    SUB_WIDTH = 2*SUB_HEIGHT
    total_neurons = WIDTH*HEIGHT
    neurons_per_core = SUB_HEIGHT*SUB_WIDTH
    nb_cores = math.ceil(total_neurons / neurons_per_core)
    print(f"For {WIDTH}x{HEIGHT} {nb_cores} cores with {neurons_per_core} neurons (for a total of {total_neurons} neurons)")

#################################################################################################################################
#                                                           SPIF SETUP                                                          #
#################################################################################################################################

# Device parameters are "pipe", "chip_coords", "ip_address", "port"
DEVICE_PARAMETERS = (0, (0, 0), "172.16.223.98", 3333)

send_fake_spikes = True

# An event frame has 32 bits <t[31]><x [30:16]><p [15]><y [14:0]>
P_SHIFT = 15
Y_SHIFT = 0
X_SHIFT = 16

if send_fake_spikes:
    WIDTH = 8
    HEIGHT = round(WIDTH*3/4)
else:
    WIDTH = 346
    HEIGHT = 260
# Creates 512 neurons per core
SUB_HEIGHT = max(2,2**math.ceil(math.log(math.ceil(math.log(max(2,int(HEIGHT*WIDTH/256)),2)),2)))
SUB_WIDTH = 2*SUB_HEIGHT

print(f"Creating {SUB_WIDTH}*{SUB_HEIGHT}={SUB_WIDTH*SUB_HEIGHT} neurons per core")

# Weight of connections between "layers"
WEIGHT = 100



# Used if send_fake_spikes is True
SLEEP_TIME = 0.005
N_PACKETS = 1000

# Run time if send_fake_spikes is False
RUN_TIME = 20000 #[ms]

print(f"SPIF : {DEVICE_PARAMETERS[2]}:{DEVICE_PARAMETERS[3]}")
print(f"Pixel Matrix : {WIDTH}x{HEIGHT} (Real={not send_fake_spikes})")
print(f"Run Time : {RUN_TIME}")
# pdb.set_trace()

#################################################################################################################################
#                                                                                                                               #
#################################################################################################################################

'''
This function returns a port number to be used during SpikeLiveConnection
'''
def get_port(first_val):
    count = 0
    while True:
        count += 1
        yield first_val + count

'''
This is what's done whenever the CPU receives a spike sent by SpiNNaker
'''
def receive_spikes_from_sim(label, time, neuron_ids):

    global end_of_sim, input_q, output_q
    
    for n_id in neuron_ids:
        # print(f"Spike --> MN[{n_id}]")
        output_q.put(n_id, False)

''' 
This function creates a list of weights to be used when connecting pixels to motor neurons
'''
def create_conn_list(w, h):
    w_fovea = 0.5
    conn_list = []
    

    delay = 1 # 1 [ms]
    for y in range(h):
        for x in range(w):
            pre_idx = y*w+x

            for post_idx in range(4):

                weight = 0.000001
                x_weight = 2*w_fovea*(abs((x+0.5)-w/2)/(w-1))
                y_weight = 2*w_fovea*(abs((y+0.5)-h/2)/(h-1))

                # Move right (when stimulus on the left 'hemisphere')    
                if post_idx == 0:
                    if (x+0.5) < w/2:
                        weight = x_weight
                            
                # Move Left (when stimulus on the right 'hemisphere')
                if post_idx == 1:
                    if (x+0.5) > w/2:
                        weight = x_weight
                                    
                # Move up (when stimulus on the bottom 'hemisphere')    
                if post_idx == 2: 
                    if (y+0.5) > h/2: # higher pixel --> bottom of image
                        weight = y_weight
                
                # Move down (when stimulus on the top 'hemisphere') 
                if post_idx == 3:
                    if (y+0.5) < h/2: # lower pixel --> top of image
                        weight = y_weight
                
                conn_list.append((pre_idx, post_idx, weight, delay))
        


    return conn_list



def send_retina_input(ip_addr, port):

    global end_of_sim

    """ 
    This is used to send random input to the Ethernet listening in SPIF
    """
    global X_SHIFT, Y_SHIFT, P_SHIFT, SLEEP_TIME, N_PACKETS
    NO_TIMESTAMP = 0x80000000
    polarity = 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    q_idx = 0
    quadrant = [(3,3),(1,3),(3,1),(1,1)]


    dt = 1 # in seconds
    
    start = time.time()
    current_t = time.time()
    next_check = current_t + dt

    n_spikes = 10
    while True:

        # Check if the spinnaker simulation has ended
        if end_of_sim.value == 1:
            time.sleep(1)
            print("No more events to be created")
            break
        
        current_t = time.time()
        if current_t >= next_check:
            # update q_idx
            q_idx += 1
            print(f"@ t = {current_t} move to quadrant #{q_idx%4}")
            next_check = current_t + dt
        
        x = int(WIDTH*quadrant[q_idx%4][0]/4)
        y = int(HEIGHT*quadrant[q_idx%4][1]/4)
        data = b""
        for _ in range(n_spikes):
            packed = (
                NO_TIMESTAMP + (polarity << P_SHIFT) +
                (y << Y_SHIFT) + (x << X_SHIFT))
            # print(f"Sending x={x}, y={y}, polarity={polarity}, "
            #     f"packed={hex(packed)}")

            data += pack("<I", packed)
        sock.sendto(data, (ip_addr, port))
        sleep(0.010) # Every 1ms one packet of n_spikes is created


            

            
def new_send_retina_input(ip_addr, port):

    global end_of_sim, input_q

    """ 
    This is used to send random input to the Ethernet listening in SPIF
    """
    global X_SHIFT, Y_SHIFT, P_SHIFT, SLEEP_TIME, N_PACKETS
    NO_TIMESTAMP = 0x80000000
    polarity = 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


    

    while True:

        # Check if the spinnaker simulation has ended
        if end_of_sim.value == 1:
            time.sleep(1)
            print("No more events to be created")
            break
        
        events = []
        while not input_q.empty():
            events = input_q.get(False)


        data = b""
        for e in events:        
            x = e[0]
            y = e[1]
        
            packed = (
                NO_TIMESTAMP + (polarity << P_SHIFT) +
                (y << Y_SHIFT) + (x << X_SHIFT))
            # print(f"Sending x={x}, y={y}, polarity={polarity}, "
            #     f"packed={hex(packed)}")

            data += pack("<I", packed)
        sock.sendto(data, (ip_addr, port))




def start_fake_senders():

    global DEVICE_PARAMETERS

    ip_addr = DEVICE_PARAMETERS[2]
    port = DEVICE_PARAMETERS[3]
    
    t = multiprocessing.Process(target=new_send_retina_input, args=(ip_addr, port,))
    t.start()
        


#################################################################################################################################
#                                                        SPINNAKER SETUP                                                        #
#################################################################################################################################

def run_spinnaker_sim():

    global end_of_sim, input_q, output_q
    global DEVICE_PARAMETERS, P_SHIFT, Y_SHIFT, X_SHIFT, SUB_HEIGHT, SUB_WIDTH, WEIGHT, RUN_TIME

    cell_params = {'tau_m': 20.0,
                'tau_syn_E': 5.0,
                'tau_syn_I': 5.0,
                'v_rest': -65.0,
                'v_reset': -65.0,
                'v_thresh': -50.0,
                'tau_refrac': 0.0, # 0.1 originally
                'cm': 1,
                'i_offset': 0.0
                }

    celltype = p.IF_curr_exp

    # Set up PyNN


    p.setup(timestep=1.0, n_boards_required=1)     

    # Set the number of neurons per core 
    p.set_number_of_neurons_per_core(p.IF_curr_exp, SUB_HEIGHT*SUB_WIDTH)

    if send_fake_spikes:
        # This is only used with the above to send data to the Ethernet
        connection = DatabaseConnection(start_fake_senders, local_port=None)

        print(f"DB Connection port = {connection.local_port}")
        # time.sleep(5)

        # This is used with the connection so that it starts sending when the simulation starts
        p.external_devices.add_database_socket_address(None, connection.local_port, None)

    capture_conn = p.ConvolutionConnector([[WEIGHT]])

    # These are our external retina devices connected to SPIF devices
    devices = list()
    captures = list()
    pipe = DEVICE_PARAMETERS[0]
    chip_coords = DEVICE_PARAMETERS[1]

    dev = p.Population(None, p.external_devices.SPIFRetinaDevice(
        pipe=pipe, width=WIDTH, height=HEIGHT, sub_width=SUB_WIDTH,
        sub_height=SUB_HEIGHT, input_x_shift=X_SHIFT, input_y_shift=Y_SHIFT))

    # Create a population that captures the spikes from the input
    capture = p.Population(WIDTH * HEIGHT, p.IF_curr_exp(), 
                            structure=Grid2D(WIDTH / HEIGHT),
                            label=f"Capture for device SPIF")

    p.Projection(dev, capture, capture_conn, p.Convolution())

    # Record the spikes so we know what happened
    # capture.record("spikes")

    # Save for later use
    devices.append(dev)
    captures.append(capture)


    m_labels = ["go_right", "go_left", "go_up", "go_down"]
        


    motor_neurons = p.Population(4, celltype(**cell_params), label="motor_neurons")

    
    # motor_neurons.record("spikes")

    conn_list = create_conn_list(WIDTH, HEIGHT)



    if WIDTH < 10:
        for conn in conn_list:
            x = conn[0]%WIDTH
            y = math.floor(conn[0]/WIDTH)
            print(f"({x},{y}) : {conn[0]}\t-->\t{conn[1]} : w={conn[2]}")


    cell_conn = p.FromListConnector(conn_list, safe=True)   
    # pdb.set_trace() 
    con_move = p.Projection(capture, motor_neurons, cell_conn, receptor_type='excitatory')

        
    # Spike reception (from SpiNNaker to CPU)
    port_generator = get_port(14000)
    port = next(port_generator)
    live_spikes_receiver = p.external_devices.SpynnakerLiveSpikesConnection(receive_labels=["motor_neurons"], local_port=port)
    _ = p.external_devices.activate_live_output_for(motor_neurons, database_notify_port_num=live_spikes_receiver.local_port)
    live_spikes_receiver.add_receive_callback("motor_neurons", receive_spikes_from_sim)

    # pdb.set_trace()

    # Run the simulation for long enough for packets to be sent
    p.run(RUN_TIME)


    # # Get out the spikes

    # in_spikes = capture.get_data("spikes")
    # out_spikes = motor_neurons.get_data("spikes")

    # for h in range(HEIGHT):
    #     for w in range(WIDTH):
    #         l = len(np.asarray(in_spikes.segments[0].spiketrains[h*WIDTH+w]))
    #         print(f"({w},{h})-->{l}")

    # w_array = np.array(con_move.get("weight", format="array"))


    # Let other processes know that spinnaker simulation has come to an ned
    end_of_sim.value = 1

    # pdb.set_trace()

    # Tell the software we are done with the board
    p.end()



 
class BouncingBall:
  def __init__(self, dt, w, l, r, cx, cy, vx, vy):
    self.dt = dt
    self.r = r
    self.w = w
    self.l = l
    self.cx = cx
    self.cy = cy
    self.vx = vx
    self.vy = vy

  def update_c(self):

    marg = 1

    next_cx = self.cx+self.vx*self.dt
    next_cy = self.cy+self.vy*self.dt
    # print("nxt_center: ({:.3f}, {:.3f})".format(next_cx, next_cy))
    if self.l-self.r-marg < next_cx:
        # print("Right edge")
        next_cx = (self.l-self.r-marg)-(next_cx-(self.l-self.r-marg))
        self.vx = -self.vx
    if marg+self.r > next_cx:
        # print("Left edge")
        next_cx = marg+self.r-(next_cx-(marg+self.r))
        self.vx = -self.vx
    self.cx = next_cx
    
    if self.w-self.r-marg < next_cy:
        # print("Bottom edge")
        next_cy = (self.w-self.r-marg)-(next_cy-(self.w-self.r-marg))
        self.vy = -self.vy
        
    if marg+self.r > next_cy:
        # print("Top edge")
        next_cy = marg+self.r-(next_cy-(marg+self.r))
        self.vy = -self.vy
    self.cy = next_cy


def ring(r):
    cir = np.zeros((2*r+1, 2*r+1))
    idx = np.array(range(-r, r+1, 1))
    for x in idx:
        for y in idx:
            d = math.sqrt(x*x+y*y)
            if d <= r and d > r-2:
                cir[r+x, r+y] = 1         
                
    return cir 

def circle(r):
    cir = np.zeros((2*r+1, 2*r+1))
    idx = np.array(range(-r, r+1, 1))
    for x in idx:
        for y in idx:
            d = math.sqrt(x*x+y*y)
            if d <= r:
                cir[r+x, r+y] = 1         
                
    return cir

def update_pixel_frame(bball, LED_on):
    
    mat = np.zeros((bball.w,bball.l))

    events = []

    if LED_on:
        cir = ring(bball.r)
        cx = int(bball.cx)
        cy = int(bball.cy)
        mat[cy-bball.r:cy+bball.r+1, cx-bball.r:cx+bball.r+1] = cir  

        for y in range(cy-bball.r,cy+bball.r+1,1):
            for x in range(cx-bball.r,cx+bball.r+1,1):
                events.append((x, y))
    

    return mat, events 

def set_inputs():

    global end_of_sim, input_q, object_q

    dt = 1 #ms
    l = WIDTH
    w = HEIGHT
    r = min(8, int(WIDTH*7/637+610/637))
    print(r)
    cx = int(l/2)
    cy = int(w/2)
    vx = -WIDTH/100
    vy = HEIGHT/200
    duration = 60


    
    bball = BouncingBall(dt, w, l, r, cx, cy, vx, vy)

    fps = 50
    LED_f = 200
    ball_update = 0
    LED_update = 0
    LED_on = 1
    t = 0

    while True:

        # Check if the spinnaker simulation has ended
        if end_of_sim.value == 1:
            time.sleep(1)
            print("No more inputs to be sent")
            break
    
        if LED_update >= 1000/LED_f:
            LED_update = 0
            LED_on = 1 - LED_on

        mat, events = update_pixel_frame(bball, LED_on)

        if ball_update >= 1000/fps:
            ball_update = 0      
            bball.update_c()


            # im_final = cv2.resize(mat*255,(640,480), interpolation = cv2.INTER_NEAREST)
            # cv2.imshow("Pixel Space", im_final)
            # cv2.waitKey(1) 
        

        coor = [bball.cx, bball.cy]
        object_q.put(coor)
        input_q.put(events)

        ball_update += 1
        LED_update += 1
        t += 1


        time.sleep(0.001)



def get_outputs():

    global end_of_sim, input_q, output_q,  spike_q
    
    dt = 0.100
    
    start = time.time()
    current_t = time.time()
    next_check = current_t + dt

    spike_times = []
    spike_count = [0,0,0,0]
    nb_spikes_max = 100
    for i in range(4):  # 4 motor neurons          
        spike_times.append(collections.deque(maxlen=nb_spikes_max))
        
    while True:

        # Check if the spinnaker simulation has ended
        if end_of_sim.value == 1:
            time.sleep(1)
            print("No more outputs to be received")
            break

        while not output_q.empty():
            out = output_q.get(False)
            current_t = time.time()
            elapsed_t = (current_t - start)*1000
            spike_times[out].append(elapsed_t)
        
        if current_t >= next_check:
            # print(f"Checking @ t={current_t}")
            next_check = current_t + dt
            for i in range(4):  # 4 motor neurons
                train = np.array(spike_times[i])
                short_train = train[train>(current_t-dt-start)*1000]
                # print(f"For MN[{i}]: {len(train)} >= {len(short_train)} (Train vs Short Train)")
                spike_count[i] = len(short_train)
            spike_q.put(spike_count, False)

        time.sleep(0.005)

def rt_plot(i, axs, t, x, y, mn_r, mn_l, mn_u, mn_d, obj_xy, spike_count):

    global spike_q, object_q


    while not object_q.empty():
        obj_xy = object_q.get(False)
        # print(spike_count)

    while not spike_q.empty():
        spike_count = spike_q.get(False)

    # Add x and y to lists
    t.append(datetime.datetime.now().strftime('%H:%M:%S.%f'))

    x.append(obj_xy[0])
    y.append(obj_xy[1])

    mn_r.append(spike_count[0])
    mn_l.append(spike_count[1])
    mn_u.append(spike_count[2])
    mn_d.append(spike_count[3])

    # Limit x and y lists to 100 items
    t = t[-100:]
    x = x[-100:]
    y = y[-100:]
    mn_r = mn_r[-100:]
    mn_l = mn_l[-100:]
    mn_u = mn_u[-100:]
    mn_d = mn_d[-100:]

    txt_x = txt_y = txt_l = txt_r = txt_u = txt_d = ""
    if x[-1] != -100:
        txt_x = "x = {:.3f} [m] ".format(x[-1]) 
    if y[-1] != -100:
        txt_y = "y = {:.3f} [m] ".format(y[-1])
    if mn_r[-1] != -100:
        txt_r = "r = {:.3f} [m] ".format(mn_r[-1]) 
    if mn_l[-1] != -100:
        txt_l = "l = {:.3f} [m] ".format(mn_l[-1]) 
    if mn_u[-1] != -100:
        txt_u = "u = {:.3f} [m] ".format(mn_u[-1]) 
    if mn_d[-1] != -100:
        txt_d = "d = {:.3f} [m] ".format(mn_d[-1])

    # Draw x and y lists

    max_y = int(1.2*max(WIDTH, HEIGHT))


    axs[0].clear()
    axs[0].plot(t, x)
    axs[0].plot(t, y)
    axs[0].text(t[0], 0.75*max_y, txt_x, fontsize='xx-large')
    axs[0].text(t[0], 0.15*max_y, txt_y, fontsize='xx-large')
    axs[0].xaxis.set_visible(False)
    axs[0].set_ylabel('Pixels')
    axs[0].set_ylim([0,max_y])

    max_y = 100

    axs[1].clear()
    axs[1].plot(t, mn_r, color='r')
    axs[1].text(t[0], 0.75*max_y, txt_r, fontsize='xx-large')
    axs[1].xaxis.set_visible(False)
    axs[1].set_ylabel('mn_r')
    axs[1].set_ylim([0,max_y])

    axs[2].clear()
    axs[2].plot(t, mn_l, color='g')
    axs[2].text(t[0], 0.75*max_y, txt_l, fontsize='xx-large')
    axs[2].xaxis.set_visible(False)
    axs[2].set_ylabel('mn_l')
    axs[2].set_ylim([0,max_y])

    axs[3].clear()
    axs[3].plot(t, mn_u, color='r')
    axs[3].text(t[0], 0.75*max_y, txt_u, fontsize='xx-large')
    axs[3].xaxis.set_visible(False)
    axs[3].set_ylabel('mn_u')
    axs[3].set_ylim([0,max_y])

    axs[4].clear()
    axs[4].plot(t, mn_d, color='g')
    axs[4].text(t[0], 0.75*max_y, txt_d, fontsize='xx-large')
    axs[4].xaxis.set_visible(False)
    axs[4].set_ylabel('mn_d')
    axs[4].set_ylim([0,max_y])


    axs[0].set_title("Motor Neurons", fontsize='xx-large')

def oscilloscope():


    print("Starting Oscilloscope")

    # Create figure for plotting
    fig, axs = plt.subplots(5, figsize=(8, 8))
    fig.canvas.manager.set_window_title('World Space')


    t = []
    x = []
    y = []
    mn_r = []
    mn_l = []
    mn_u = []
    mn_d = []

    i = 0
    spike_count = [-100,-100,-100,-100]
    obj_xy = [-100,-100]

    # Set up plot to call rt_xyz() function periodically
    ani = animation.FuncAnimation(fig, rt_plot, fargs=(axs, t, x, y, mn_r, mn_l, mn_u, mn_d, obj_xy, spike_count), interval=1)
    plt.show()

if __name__ == '__main__':

    global end_of_sim, input_q, output_q, spike_q, object_q
    
    print("\n About to start things ... \n")

    time.sleep(3)

    manager = multiprocessing.Manager()

    end_of_sim = manager.Value('i', 0)
    input_q = multiprocessing.Queue()
    output_q = multiprocessing.Queue()
    spike_q = multiprocessing.Queue()
    object_q = multiprocessing.Queue()




    p_i_data = multiprocessing.Process(target=set_inputs, args=())
    p_o_data = multiprocessing.Process(target=get_outputs, args=())
    p_visual = multiprocessing.Process(target=oscilloscope, args=())
    # p_spinn = multiprocessing.Process(target=run_spinnaker_sim, args=())
    

    p_i_data.start()
    p_o_data.start()
    p_visual.start()
    # p_spinn.start()

    run_spinnaker_sim()

    p_i_data.join()
    p_o_data.join()
    p_visual.join()
    # p_spinn.join()