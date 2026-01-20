#  Copyright (c) Michele De Stefano - 2026.

from elegoo_robot_car4 import Car


def test_get_mpu_data(car: Car) -> None:
    # given, when
    data = car.get_mpu_data()
    # then
    assert "MPU_Request_" in data["id"]
    assert data["t"] != int(data["t"]), "floating point time returned"
    assert len(data["a"]) == 3
    assert len(data["g"]) == 3


def test_get_ultrasonic_value(car: Car) -> None:
    # given, when
    distance = car.get_ultrasonic_value()
    # then
    assert distance != int(distance), "Floating point distance returned"


def test_check_obstacle(car: Car) -> None:
    # given, when
    result = car.check_obstacle()
    # then
    assert isinstance(result, bool), "Check obstacle result returned"


def test_get_ir_value(car: Car) -> None:
    # given, when
    result = car.get_ir_value(Car.IR_MIDDLE)
    # then
    assert isinstance(result, int), "IR_MIDDLE result returned"


def test_get_ir_all(car: Car) -> None:
    # given, when
    result = car.get_ir_all()
    # then
    assert (
        result[Car.IR_LEFT] == result[Car.IR_RIGHT] == result[Car.IR_MIDDLE]
    ), "Dummy check for IR readings succeeded"


def test_is_far_from_the_ground(car: Car) -> None:
    # given, when
    result = car.is_far_from_the_ground()
    # then
    assert isinstance(result, bool), "is_far_from_the_ground result returned"


def test_clear_all_states(car: Car) -> None:
    # Test passes if no exception is thrown
    car.clear_all_states()


def test_set_mode(car: Car) -> None:
    # Test passes if no exception is thrown
    car.set_mode(Car.FOLLOW_MODE)
    car.set_mode(Car.TRACKING_MODE)
    car.set_mode(Car.OBSTACLE_AVOIDANCE_MODE)


def test_immediate_movement(car: Car) -> None:
    # Test passes if no exception is thrown
    car.forward()
    car.backward()
    car.left()
    car.right()
    car.forward_left()
    car.forward_right()
    car.backward_left()
    car.backward_right()
    car.stop()
    car.forward_until(has_to_stop=lambda: True)


def test_set_head_angle(car: Car) -> None:
    # given
    new_angle = 45

    # when
    car.set_head_angle(angle=new_angle)

    # then
    expected_angle = new_angle
    actual_angle = car.head_angle
    assert expected_angle == actual_angle


def test_lazy_set_head_angle(car: Car) -> None:
    # given
    new_angle = 45

    # when
    car.set_head_angle(angle=new_angle, lazy=True)
    car.move()

    # then
    expected_angle = new_angle
    actual_angle = car.head_angle
    assert expected_angle == actual_angle


def test_turn_head(car: Car) -> None:
    # Test passes if no exception is thrown
    car.turn_head(delta=-30)
