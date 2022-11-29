
import multiprocessing 
import socket
import pdb
import math
import sys
import datetime
import time
import numpy as np
import random
from struct import pack
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame


# An event frame has 32 bits <t[31]><x [30:16]><p [15]><y [14:0]>
P_SHIFT = 15
Y_SHIFT = 0
X_SHIFT = 16

class Stimulator:
    def __init__(self, args, end_of_sim):
        self.display = []
        self.gui = args.gui
        self.ip_addr = args.ip
        self.port = args.port
        self.w = args.width
        self.h = self.w+0*int(args.width*3/4)
        self.mode = args.mode # Automatic
        self.display_size = (346, int(self.h*346/self.w))
        self.input_q = multiprocessing.Queue()
        self.control_q = multiprocessing.Queue()
        self.end_of_sim = end_of_sim
        self.pix_mat_mp = multiprocessing.Array('I', int(np.prod((self.w, self.h))), lock=multiprocessing.Lock())
        self.pix_mat_np = np.frombuffer(self.pix_mat_mp.get_obj(), dtype='I').reshape((self.w, self.h))
        self.shared_pix_mat = (self.pix_mat_mp, self.pix_mat_np)
        if self.gui == 1:
            self.p_screen = multiprocessing.Process(target=self.show_screen, args=())
        self.p_i_data = multiprocessing.Process(target=self.set_inputs, args=())
        self.p_stream = multiprocessing.Process(target=self.launch_input_handler, args=())

    
    def __enter__(self):
  
        # pygame.display.set_caption("Lala")
        if self.gui == 1:
            pygame.init()   
            self.p_screen.start()
        self.p_i_data.start()
        self.p_stream.start()
    
    def __exit__(self, e, b, t): 
        if self.gui == 1:
            pygame.quit()
            self.p_screen.join()
        self.p_i_data.join()
        self.p_stream.join()
    

    def set_inputs(self):

        dt = 1 #ms
        l = self.w
        w = self.h
        r = min(8, 2*int(self.w*7/637+610/637))
        print(r)
        cx = int(l*1/4)
        cy = int(w*2/4)
        vx = -self.w/400
        vy = self.h/1000
        mode = self.mode


        
        bball = BouncingBall(dt, w, l, r, cx, cy, vx, vy, mode)

        fps = 50
        LED_f = 200
        ball_update = 0
        LED_update = 0
        LED_on = 1
        t = 0

        while True:

            # Check if the spinnaker simulation has ended
            if self.end_of_sim.value == 1:
                time.sleep(1)
                print("No more inputs to be sent")
                break
        
            if LED_update >= 1000/LED_f:
                LED_update = 0
                LED_on = 1 - LED_on

            mat, events = bball.update_frame(LED_on)
            if LED_on:
                pix_mat_mp, pix_mat_np = self.shared_pix_mat
                pix_mat_np[:,:] = np.transpose(mat)

            if ball_update >= 1000/fps:
                ball_update = 0      
                dx = 0
                dy = 0
                while not self.control_q.empty():
                    command = self.control_q.get(False)
                    if command == 'up':
                        dy = -1   
                    if command == 'down':
                        dy = 1   
                    if command == 'left':
                        dx = -1
                    if command == 'right':
                        dx = 1
                bball.update_center(dx, dy)

            
            self.input_q.put(events)

            ball_update += 1
            LED_update += 1
            t += 1


            time.sleep(0.0001)

    def launch_input_handler(self):

        NO_TIMESTAMP = 0x80000000
        polarity = 1

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


        while True:

            # Check if the spinnaker simulation has ended
            if self.end_of_sim.value == 1:
                time.sleep(1)
                print("No more events to be created")
                break
            
            events = []
            while not self.input_q.empty():
                events = self.input_q.get(False)


            data = b""
            for e in events:        
                x = e[0]
                y = e[1]
            
                packed = (
                    NO_TIMESTAMP + (polarity << P_SHIFT) +
                    (y << Y_SHIFT) + (x << X_SHIFT))

                data += pack("<I", packed)
            sock.sendto(data, (self.ip_addr, self.port))


    def update_screen(self):

        pix_mat_mp, pix_mat_np = self.shared_pix_mat
        
        image = np.zeros((pix_mat_np.shape[0],pix_mat_np.shape[1],3))
        image[:,:,1] = pix_mat_np*255

        return image.astype('uint8')

    def show_screen(self):

        go_up = False
        go_down = False
        go_left = False
        go_right = False

        self.display = pygame.display.set_mode(self.display_size)
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        go_up = True # print(u"\u2191")
                    if event.key == pygame.K_DOWN:
                        go_down = True # print(u"\u2193")
                    if event.key == pygame.K_LEFT:
                        go_left = True # print(u"\u2190")
                    if event.key == pygame.K_RIGHT:
                        go_right = True # print(u"\u2192")
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_UP:
                        go_up = False
                    if event.key == pygame.K_DOWN:
                        go_down = False
                    if event.key == pygame.K_LEFT:
                        go_left = False
                    if event.key == pygame.K_RIGHT:
                        go_right = False
            
            if go_up:
                self.control_q.put('up')
            if go_down:
                self.control_q.put('down')
            if go_left:
                self.control_q.put('left')
            if go_right:
                self.control_q.put('right')


            Z = self.update_screen()
            surf = pygame.surfarray.make_surface(Z)
            surf = pygame.transform.scale(surf, self.display_size)

            self.display.blit(surf, (0, 0))

            pygame.display.update()  


class BouncingBall:

    def __init__(self, dt, w, l, r, cx, cy, vx, vy, mode):

        self.dt = dt
        self.r = r
        self.w = w
        self.l = l
        self.cx = cx
        self.cy = cy
        self.vx = vx
        self.vy = vy
        self.mode = mode

    def update_center(self, dx=0, dy=0):

        marg = 1

        if self.mode == 'auto':
            next_cx = self.cx+self.vx*self.dt
            next_cy = self.cy+self.vy*self.dt
        else:
            next_cx = self.cx + dx
            next_cy = self.cy + dy
            
        if self.l-self.r-marg < next_cx:
            next_cx = self.l-self.r-marg 
            self.vx = -self.vx
        if marg+self.r-1 > next_cx:
            next_cx = marg+self.r-1 
            self.vx = -self.vx
        self.cx = next_cx

        if self.w-self.r-marg < next_cy:
            next_cy = self.w-self.r-marg 
            self.vy = -self.vy
            
        if marg+self.r-1 > next_cy:
            next_cy = marg+self.r-1 
            self.vy = -self.vy
        self.cy = next_cy

    def circle(self, r):
        cir = np.zeros((2*r+1, 2*r+1))
        idx = np.array(range(-r, r+1, 1))
        for x in idx:
            for y in idx:
                d = math.sqrt(x*x+y*y)
                if d <= r and d >= r*3/4:
                    cir[r+x, r+y] = 1         
                    
        return cir

    def update_frame(self, LED_on):
        
        mat = np.zeros((self.w,self.l))

        events = []

        if LED_on:
            cir = self.circle(self.r)
            cx = int(self.cx)
            cy = int(self.cy)
            mat[cy-self.r:cy+self.r+1, cx-self.r:cx+self.r+1] = cir  

            for y in range(cy-self.r,cy+self.r+1,1):
                for x in range(cx-self.r,cx+self.r+1,1):
                    events.append((x, y))
        

        return mat, events 