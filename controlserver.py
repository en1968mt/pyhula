import http
from tkinter.messagebox import NO




#import serial.tools.list_ports
import datetime
import os

import enum
import time
import threading
from ..system.taskcontroller import TaskController, UserTask, SysTask
from ..system.datacenter import *


from time import ctime
import time
from ..system.state import SysState
import psutil
import socket
from . import config
################################tcp###################################
ConnectType = enum.Enum('ConnectType', ('Serial', 'Network', 'Tcpwork'))

class Token:
    __instance = None

    def __new__(cls):
        if cls.__instance == None:
            cls.__instance = object.__new__(cls)
            cls.__instance._flag = 1
            return cls.__instance
        else:
            return cls.__instance

    def __init__(self):
        if self._flag == 1:
            self._flag = 0
            self._token = 0
            self._lock = threading.Lock()

    def get_token(self):
        self._token += 1
        if self._token > 255:
            self._token = 1

        return self._token



def get_wifi_ip():
    #
    info = psutil.net_if_addrs()

    # WiFi
    for interface_name, addresses in info.items():
        # IPv4
        for addr in addresses:
            if addr.family == socket.AF_INET:
                # 'Wi-Fi', 'WLAN',  'wlan'
                if 'wi-fi' in interface_name.lower() or 'wlan' in interface_name.lower():
                    return interface_name, addr.address

    return None, None

class Controlserver:
    def __init__(self):
        self._connect_status = 0
        self._datacenter = DataCenter()


    # =============================================System Config======================================================================#

    def connect(self, server_ip):
        self._connect_status = 1
        if server_ip == None:
            interface_name, ip_address = get_wifi_ip()

            server_ip = ip_address
        if  server_ip == None:
            return False
        self._taskcontroller = TaskController(server_ip)
        # data = self._taskcontroller._wait_state(SysState.P_State_GetHeartbeat, 5)
        time.sleep(3)
        data =  self._datacenter.get_data('Plane','heartbeat')
        if data == None:
            print('connect error')

            return False
        print('connect wifi')
        self._taskcontroller.create_task(UserTask.S_Fly_Plane_time,{'plane_id': 1})
        self._taskcontroller.udp_heartbeat_send_thread()
        return True


    def disconnect(self):
        if self._connect_status == 1:
            self._taskcontroller.stop_all_task()
            # self._communication_controller.disconnect()
            # self._datacenter.empty_datacenter()
            self._connect_status = 0


    def get_Image_array(self):
        return self._taskcontroller.getImage_array()
    # =============================================RealTime Control===================================================================#
    #
    def planeDate_decorator(func):

        def wrapper(self,*args,**kw):
            _token = Token().get_token()
            func(self, *args, _token, **kw)

            data = self._taskcontroller._wait_state(SysState.P_Ack_GetFormation, 20)

            if data:
                # If result is 255 and token matches, return True
                  if data.get('result') == 255 and data.get('token') == _token:
                      return True
                # If result is 240 and it's the first retry, retry the wrapper function

                  else:
                    return False
            else:
                return False
            # If data is empty or other cases, return False


        return wrapper



    #8.Linux
    def Plane_Linux_cmd(self, cmd, ack, type, data, reserve):

        self._taskcontroller.create_task(UserTask.S_Fly_Linux_cmd,{'_token': 0, 'plane_id': 0, 'cmd': cmd, 'ack': ack, 'type': type, 'data': data, 'reserve': reserve})


    def Plane_getBarrier(self):

        data =  self._datacenter.get_data('Plane','flight_data')
        _barrierList = {
            'forward': False,
            'back': False,
            'left': False,
            'right': False,

        }
        if data == None:
            return _barrierList

        barrier = data.barrier
        # m_DownBarrier = (barrier & 16) == 16
        _barrierList['forward'] = (barrier & 1) == 1
        _barrierList['back'] = (barrier & 2) == 2
        _barrierList['left'] = (barrier & 4) == 4
        _barrierList['right'] = (barrier & 8) == 8
        time.sleep(0.1)
        return _barrierList
    def get_battery(self):
        data =  self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return 0
        time.sleep(0.1)
        return data.battery_volumn
    def get_coordinate(self):
        data =  self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return [0,0,0]
        time.sleep(0.1)
        return[int(data.x),int(data.y),int(data.z)]
    def get_laser_receiving(self):

        data = self._taskcontroller._wait_state(SysState.P_State_Photoresponse, 1)
        if data == None:
            return False
        return data.get('cmd') == 7
    def get_yaw(self):
        data = self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return [0,0,0]
        time.sleep(0.1)
        return[int(data.yaw/100),int(data.pitch/100),int(data.roll/100)]

    def get_accelerated_speed(self):
        data = self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return [0,0,0]
        time.sleep(0.1)
        return[int(data.accx),int(data.accy),int(data.accz)]

    def get_plane_speed(self):
        data = self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return [0,0,0]
        time.sleep(0.1)
        return[int(data.vel_x),int(data.vel_y),int(data.vel_z)]

    def get_plane_distance(self):
        data = self._datacenter.get_data('Plane','flight_data')
        if data == None:
            return 0
        time.sleep(0.1)
        return int(data.distance)
    def get_plane_id(self):
        time.sleep(0.1)
        return config.drone_id

    # 改造ポイント2: 主要センサーをまとめて取得する
    def get_sensor_data(self):
        return {
            'battery': self.get_battery(),
            'coordinate': self.get_coordinate(),
            'yaw': self.get_yaw(),
            'accel': self.get_accelerated_speed(),
            'speed': self.get_plane_speed(),
            'tof_distance': self.get_plane_distance(),
            'barrier': self.Plane_getBarrier(),
        }


    def single_fly_lamplight(self, r, g, b, time, mode , token = 0):
        # print(self._taskcontroller._datacenter.get_data(Device.Plane,SysState.P_State_GetHeartbeat,1),8888888888888)
        return self._taskcontroller.create_task(UserTask.S_Fly_Lamplight, {'_token': token, 'plane_id': 1, 'r': r, 'g': g, 'b': b,'mode': mode,'time': time})
    # @planeDate_decorator
    def single_fly_takeoff(self, led, height = 50, token = 0):
        # 改造ポイント1: heightを引数化。元は 'height': 100 に固定されていた
        data =  self._datacenter.get_data('Plane','heartbeat')
        if data !=None and data.drone_status == 2:
           return self._taskcontroller.create_task(UserTask.S_Fly_Takeoff, {'_token': token, 'plane_id': 1, 'height': height,'led': led})
        else:
           print('plane-status error')
           os._exit(0)

    # @planeDate_decorator
    def single_fly_touchdown(self,  led, token = 0):
        return  self._taskcontroller.create_task(UserTask.S_Fly_Touchdown, {'_token': token, 'plane_id': 1,'led': led})
    # @planeDate_decorator
    def single_fly_forward(self, distance, speed, led, token = 0):
        return self._taskcontroller.create_task(UserTask.S_Fly_Forward, {'_token': token, 'plane_id': 1, 'distance': distance,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_back(self, distance, speed, led, token = 0):

        return self._taskcontroller.create_task(UserTask.S_Fly_Back, {'_token': token, 'plane_id': 1, 'distance': distance,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_left(self,  distance, speed, led, token = 0):
        return self._taskcontroller.create_task(UserTask.S_Fly_Left, {'_token': token, 'plane_id': 1, 'distance': distance,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_right(self,  distance, speed, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_Right, {'_token': token, 'plane_id': 1, 'distance': distance,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_up(self,  height, speed, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_Up, {'_token': token, 'plane_id': 1, 'height': height,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_down(self, height, speed, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_Down, {'_token': token, 'plane_id': 1, 'height': height,'led': led, 'speed': speed})
    # @planeDate_decorator
    def single_fly_turnleft(self, angle, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_TurnLeft, {'_token': token, 'plane_id': 1, 'angle': angle,'led': led})
    # @planeDate_decorator
    def single_fly_turnright(self,  angle, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_TurnRight, {'_token': token, 'plane_id': 1, 'angle': angle,'led': led})

    # @planeDate_decorator
    def single_fly_radius_around(self, radius, led, token = 0):
       return self._taskcontroller.create_task(UserTask.S_Fly_RadiusAround, {'_token': token, 'plane_id': 1, 'radius': radius,'led': led})
    # @planeDate_decorator
    def single_fly_curvilinearFlight(self, direction, x, y, z, speed, led, token = 0):
        return self._taskcontroller.create_task(UserTask.S_Fly_CurvilinearFlight, {'_token': token, 'plane_id': 1, 'x': x, 'y': y, 'z': z, 'direction':direction, 'led': led, 'speed': speed})

    # @planeDate_decorator
    def single_fly_autogyration360(self,  num, led, token = 0):
        return self._taskcontroller.create_task(UserTask.S_Fly_TurnLeft360, {'_token': token, 'plane_id': 1,  'num':num, 'led': led})

    # def single_fly_turnright360(self,   num, token = 0):

    # @planeDate_decorator
    def single_fly_hover_flight(self, time, led, token = 0):
        return  self._taskcontroller.create_task(UserTask.S_Fly_HoverFlight, {'_token': token, 'plane_id': 1, 'time': time, 'led': led})

    # @planeDate_decorator
    def single_fly_bounce(self, frequency, height, led, token = 0):
        return self._taskcontroller.create_task(UserTask.S_Fly_Bounce, {'_token': token, 'plane_id': 1, 'height': height,'frequency':frequency, 'led': led})

    # @planeDate_decorator
    def single_fly_straight_flight(self,  x, y, z, speed, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_StraightFlight, {'_token': token, 'plane_id': 1, 'x': x, 'y': y, 'z': z, 'led': led, 'speed': speed})

    # @planeDate_decorator
    def single_fly_barrier_aircraft(self, mode,  token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_Barrier_aircraft,{'_token': token, 'plane_id': 1 ,'mode': mode})
    # @planeDate_decorator
    def single_fly_somersault(self, direction, led, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_FlipForward, {'_token': token, 'plane_id':1,'direction': direction, 'led': led})

    def single_fly_flip_back(self, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_FlipBack, {'_token': token, 'plane_id':1})

    def single_fly_flip_left(self, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_FlipLeft, {'_token': token, 'plane_id':1})

    def single_fly_flip_right(self, token = 0):
        self._taskcontroller.create_task(UserTask.S_Fly_FlipRight, {'_token': token, 'plane_id':1})

    def single_fly_flip_rtp(self):
        self._taskcontroller.udp_rtp_udp_recive_thread()

    def single_fly_Line_walking(self, fun_id, dist, tv, way_color):
        self._taskcontroller.create_task(UserTask.S_Fly_Line_walking, {'fun_id': fun_id, 'dist': dist, 'tv': tv , 'way_color':way_color})
        while True:

            data = self._taskcontroller._wait_state(SysState.P_State_WALKING,0.5)
            if data == None:
                continue
            time.sleep(0.5)
            return data


    def single_fly_AiIdentifies(self,mode):
        self._taskcontroller.create_task(UserTask.S_Fly_AiIdentifies,{'mode':mode})
        _data = {'mode':0,'type': 0,'x':0,'y':0,'z':0,'angle':0,'result':False}
        while True:
              data = self._taskcontroller._wait_state(SysState.P_State_CAMERA, 0.5)


              if data == None :
                 continue
              _data['mode'] = data['mode']
              _data['type'] = data['type']
            #   _data['time_duration'] = data['time_duration']
              _data['x'] = int(data['x']*100)
              _data['y'] = int(data['y']*100)
              _data['z'] = int(data['z']*100)
              _data['angle'] = int(data['angle'])
              _data['result'] = data['result'] == 1
              time.sleep(0.5)
              return _data

    def single_fly_Qrcode_tracking(self, mode, type, time_duration):
        self._taskcontroller.create_task(UserTask.S_Fly_Qr_tracking,{'mode':mode,'type': type,'time_duration': time_duration })
        _data = {'mode':0,'type': 0,'x':0,'y':0,'z':0,'angle':0,'result':False}
        while True:
              data = self._taskcontroller._wait_state(SysState.P_State_CAMERA, 0.5)
              if data == None :
                  continue
              _data['mode'] = data['mode']
              _data['type'] = data['type']
            #   _data['time_duration'] = data['time_duration']
              _data['x'] = int(data['x']*100)
              _data['y'] = int(data['y']*100)
              _data['z'] = int(data['z']*100)
              _data['angle'] = int(data['angle']*100)
              _data['result'] = data['result'] == 1
              time.sleep(0.5)
              return _data


    def single_fly_Qrcode_align(self, mode, time_duration, search_radius, qr_id, qr_size, yaw_r):
        self._taskcontroller.create_task(UserTask.S_Fly_Qr_align,{'mode':mode,'time_duration': time_duration, 'search_radius': search_radius,'qr_id': qr_id, 'qr_size': qr_size, 'yaw_r': yaw_r})
        _data = {'x':None,'y': None, 'z': None,'qr_id': None,'result':False,'yaw':None}
        while True:
              data = self._taskcontroller._wait_state(SysState.P_State_QRRecognite_Deal, 0.5)
              if data == None:
                  continue
              if data['status'] <= 1:
                  continue
              _data['result'] = data['status'] == 2 or data['status'] == 3
              _data['x'] = int(data['x_com'] * 100)
              _data['y'] = int(data['y_com'] * 100)
              _data['z'] = int(data['z_com'] * 100)
              _data['yaw'] = int(data['yaw_com'])
              _data['qr_id'] = data['qr_id']
              time.sleep(0.5)
              return _data


    def single_fly_getColor(self, Mode):

        self._taskcontroller.create_task(UserTask.S_Fly_ColorRecog,{'Mode':Mode})
        data = self._taskcontroller._wait_state(SysState.P_State_ColorRecog, 1)
        if data == None :
            return None
        time.sleep(0.5)
        return data

    # def multi_fly_prepare(self,'_token': token,  plane_id_start,'_token': token,  plane_id_end):
    #

    def plane_fly_arm(self, token = 0):
        data =  self._datacenter.get_data('Plane','heartbeat')

        if data !=None and data.drone_status == 2:
           return self._taskcontroller.create_task(UserTask.S_Fly_unlock, {'_token': token, 'plane_id':1})

        print('')



    def plane_fly_disarm(self, token = 0):

        return self._taskcontroller.create_task(UserTask.S_Fly_lock, {'_token': token, 'plane_id':1})


