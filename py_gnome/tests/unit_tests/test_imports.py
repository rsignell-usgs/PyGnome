"""
basic test to see if everything imports successfully
"""
import math

def test_import_gnome():
    import gnome
    
def test_import_map():
    import gnome.map

def test_import_model():
    import gnome.model

def test_import_spill():
    import gnome.spill

## import the cython extensions:

def test_import_model():
    import gnome.c_gnome

def test_import_model():
    import gnome.model

def test_import_cats_mover():
    import gnome.cats_mover
    
def test_import_random_mover():
    import gnome.random_mover

def test_import_wind_mover():
    import gnome.wind_mover
    
    
#def test_expect_to_fail():
#    import gnome.garbage
 
#def test_something():
#    assert math.pi == 3.4
    


