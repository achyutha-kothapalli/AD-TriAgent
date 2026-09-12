from app.scenarios.generate import _lane_following_steering, _vehicle_is_on_lane


class Lane:
    width = 3.5

    def local_coordinates(self, position):
        return position[0], position[1]

    def heading_theta_at(self, longitudinal):
        return 0.0


class Vehicle:
    lane = Lane()

    def __init__(self, lateral_offset: float):
        self.position = (10.0, lateral_offset)
        self.heading_theta = 0.0


def test_lane_validation_accepts_a_vehicle_inside_lane_bounds():
    assert _vehicle_is_on_lane(Vehicle(1.8))


def test_lane_validation_rejects_a_vehicle_outside_lane_bounds():
    assert not _vehicle_is_on_lane(Vehicle(2.1))


def test_lane_following_steers_towards_the_lane_center():
    assert _lane_following_steering(Vehicle(1.0)) > 0
