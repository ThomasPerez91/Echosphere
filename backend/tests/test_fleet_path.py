"""UX-API-01 pure path rules: chained routes, hop count, destination and Fog of War."""

from uuid import uuid4

from app.fleet.path import public_path, systems_along

A, B, C, D, HIDDEN = (uuid4() for _ in range(5))
KNOWN = {A, B, C, D}


def test_direct_route_gives_origin_then_destination():
    systems = systems_along(A, [(A, B)])
    assert systems == [A, B]
    assert public_path(systems, B, 1, KNOWN) == [str(A), str(B)]


def test_several_hops_keep_the_travel_order_whatever_the_stored_endpoint_order():
    # GalaxyRoute stores a_id < b_id: a route may be crossed from b to a.
    systems = systems_along(C, [(B, C), (A, B), (A, D)])
    assert systems == [C, B, A, D]
    assert public_path(systems, D, 3, KNOWN) == [str(C), str(B), str(A), str(D)]


def test_zero_hop_mission_is_the_departure_system_only():
    systems = systems_along(A, [])
    assert systems == [A]
    assert public_path(systems, A, 0, KNOWN) == [str(A)]


def test_routes_that_do_not_chain_are_never_repaired():
    assert systems_along(A, [(B, C)]) is None
    assert systems_along(A, [(A, B), (C, D)]) is None
    assert systems_along(A, [(A, B), None]) is None  # route unknown to the Empire
    assert public_path(None, B, 1, KNOWN) is None


def test_hop_count_and_destination_must_match_exactly():
    systems = systems_along(A, [(A, B), (B, C)])
    assert public_path(systems, C, 2, KNOWN) is not None
    assert public_path(systems, C, 1, KNOWN) is None  # declared hops differ
    assert public_path(systems, B, 2, KNOWN) is None  # does not end at the destination
    assert public_path(systems_along(A, []), B, 0, KNOWN) is None  # 0 hop but elsewhere


def test_fog_of_war_withholds_the_whole_path_rather_than_trimming_it():
    systems = systems_along(A, [(A, HIDDEN), (HIDDEN, B)])
    assert systems == [A, HIDDEN, B]
    assert public_path(systems, B, 2, KNOWN) is None
    assert public_path(systems, B, 2, KNOWN | {HIDDEN}) == [str(A), str(HIDDEN), str(B)]
