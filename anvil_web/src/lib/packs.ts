// Relation packs: curated collections of RSQs surfaced as quick filters in the
// catalog. A pack matches by domain prefix and/or tags, so newly seeded RSQs
// join the right pack automatically without editing this file.

import type { RegistryEntry } from "./types";

export interface Pack {
  id: string;
  label: string;
  description: string;
  /** Domain prefixes that belong to this pack (matched as `d === p` or `d.startsWith(p + ".")`). */
  domains?: string[];
  /** Any of these tags puts an RSQ in the pack. */
  tags?: string[];
}

export const PACKS: Pack[] = [
  {
    id: "jet-cycle",
    label: "Jet Engine Cycle",
    description: "GasTurb-style gas-turbine components and full engine cycles",
    domains: ["propulsion.cycle"],
  },
  {
    id: "compressible",
    label: "Compressible Flow",
    description: "Isentropic, shock, expansion, Fanno and Rayleigh duct flow",
    domains: ["aero.compressible"],
  },
  {
    id: "propulsion",
    label: "Rockets & Nozzles",
    description: "Nozzle, thrust, specific impulse and rocket equation relations",
    domains: ["propulsion"],
    tags: ["rocket", "nozzle"],
  },
  {
    id: "heat",
    label: "Heat Transfer",
    description: "Conduction, convection, radiation, heat exchangers and transients",
    domains: ["heat_transfer"],
  },
  {
    id: "fluids",
    label: "Pipe & Fluids",
    description: "Pipe friction, pressure drop and skin friction",
    domains: ["fluids"],
    tags: ["pipe", "friction"],
  },
  {
    id: "structures",
    label: "Structures",
    description: "Stress, beams, buckling, torsion and pressure vessels",
    domains: ["structures"],
  },
  {
    id: "materials",
    label: "Materials",
    description: "Safety factors, fatigue, fracture and composites",
    domains: ["materials"],
  },
  {
    id: "orbital",
    label: "Orbital & Attitude",
    description: "Orbits, transfers, attitude dynamics and ADCS sizing",
    domains: ["orbital", "attitude", "mission"],
  },
  {
    id: "controls",
    label: "Controls",
    description: "PID, transient response, stability and state-space",
    domains: ["controls"],
  },
  {
    id: "thermo",
    label: "Thermo & Cycles",
    description: "Gas properties, Carnot and Brayton cycle relations",
    domains: ["thermo"],
  },
  {
    id: "signal",
    label: "Signal & Decomposition",
    description: "FFT, spectra, filters, POD and DMD",
    tags: ["fft", "signal", "spectrum", "pod", "dmd", "filter"],
  },
  {
    id: "fitting",
    label: "Curve Fitting",
    description: "Linear, polynomial, power and exponential regression",
    domains: ["data.fitting"],
  },
];

function domainMatches(entryDomain: string, domains?: string[]): boolean {
  if (!domains) return false;
  const d = (entryDomain || "").toLowerCase();
  return domains.some((p) => d === p || d.startsWith(p.toLowerCase() + "."));
}

export function entryInPack(entry: RegistryEntry, pack: Pack): boolean {
  if (domainMatches(entry.domain, pack.domains)) return true;
  if (pack.tags) {
    const tags = (entry.tags ?? []).map((t) => t.toLowerCase());
    if (pack.tags.some((t) => tags.includes(t.toLowerCase()))) return true;
  }
  return false;
}

/** Packs that actually contain at least one of the given entries, with counts. */
export function packsWithCounts(
  entries: RegistryEntry[],
): { pack: Pack; count: number }[] {
  return PACKS.map((pack) => ({
    pack,
    count: entries.filter((e) => entryInPack(e, pack)).length,
  })).filter((p) => p.count > 0);
}
