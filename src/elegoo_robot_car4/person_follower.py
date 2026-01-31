#  Copyright (c) Michele De Stefano - 2026.
import numpy as np
from ultralytics.engine.results import Results

from elegoo_robot_car4 import Car


class PersonFollower:
    __car: Car
    __frame_shape: np.ndarray
    __center: np.ndarray

    def __init__(self, car: Car, frame_shape: np.ndarray) -> None:
        self.__car = car
        self.__frame_shape = frame_shape
        self.__center = self.__frame_shape * 0.5

    def follow(self, last_track_results: list[Results]) -> None:
        if not last_track_results:
            return
        result = last_track_results[0]
        if result.boxes.xyxy:
            box_xyxy = result.boxes.xyxy[0].numpy()
            box_center = (box_xyxy[:2] + box_xyxy[2:]) * 0.5
            displacement = box_center - self.__center
            if abs(displacement[0]) < 10:
                self.__car.stop(lazy=True)
            elif displacement[0] > 0:
                self.__car.right(lazy=True)
            else:
                self.__car.left(lazy=True)
        else:
            self.__car.stop(lazy=True)
        self.__car.move()
