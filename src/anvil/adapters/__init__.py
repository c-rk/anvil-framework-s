"""
anvil.adapters -- built-in wrappers for external libraries.

Available adapters (import individually):

    from anvil.adapters.cantera_thermo     import cea_rocket, equilibrium_flame
    from anvil.adapters.nasa_cea_detonation import cea_detonation
    from anvil.adapters.poliastro_orbits    import poliastro_orbit, poliastro_hohmann, poliastro_propagate
    from anvil.adapters.pykep_trajectories  import pykep_lambert, pykep_propagate, pykep_planet_state

M4 engineering adapters:
    from anvil.adapters.coolprop_props      import coolprop_props
    from anvil.adapters.rocket_cea          import rocket_cea, rocketpy_flight
    from anvil.adapters.meshing_geom        import mesh_box, mesh_cylinder
    from anvil.adapters.uq_surrogate         import uq_montecarlo

Optional dependencies:
    Cantera    -- conda install -c cantera cantera   (or pip install cantera)
    poliastro  -- pip install poliastro astropy
    pykep      -- pip install pykep
    CoolProp   -- pip install CoolProp                (Tier-B)
    RocketCEA  -- pip install rocketcea               (Tier A)
    RocketPy   -- pip install rocketpy                (Tier A)
    gmsh       -- pip install gmsh cadquery meshio     (Tier A)
    scikit-learn / chaospy -- pip install scikit-learn chaospy   (UQ, optional)

The M4 engineering adapters (coolprop_props, rocket_cea, rocketpy_flight,
mesh_box, mesh_cylinder) are REAL-ONLY: they have no mock fallback. The
modules import cleanly without the external package (lazy imports), but
*calling* an adapter without its package installed raises a clear
ImportError naming the package and the pip install command, e.g.
"coolprop_props requires the 'CoolProp' package; install with:
pip install CoolProp". The uq_montecarlo adapter's Monte Carlo path is
genuinely native numpy and always runs; only its optional
surrogate="sklearn" backend requires scikit-learn.
"""
