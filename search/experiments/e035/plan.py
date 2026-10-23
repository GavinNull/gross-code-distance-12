"""E-035 pre-registered task blocks and CPU allowances (copied from experiments/E-035-neutral-atom-ler.yaml)."""
FAM = {"gross": ("u11", "ibm", "fig12"), "bb90": ("c11", "ibm90")}
SENS_FAM = {"gross": ("u11", "ibm"), "bb90": ("c11", "ibm90")}
ALLOW = {  # (family, model, decoder) -> CPU seconds
    ("gross", "cur", "bposd"): 6000, ("gross", "cur", "relay5"): 3000,
    ("gross", "proj", "bposd"): 18000, ("gross", "proj", "relay5"): 8000,
    ("gross", "curx0.5", "bposd"): 18000, ("gross", "curx0.5", "relay5"): 8000,
    ("bb90", "cur", "bposd"): 2000, ("bb90", "cur", "relay5"): 1000,
    ("bb90", "proj", "bposd"): 8000, ("bb90", "proj", "relay5"): 4000,
    ("bb90", "curx0.5", "bposd"): 8000, ("bb90", "curx0.5", "relay5"): 4000,
    ("gross", "cur_cz", "bposd"): 4000, ("gross", "cur_par", "bposd"): 6000, ("gross", "cur_slow", "bposd"): 6000,
    ("gross", "proj_t2par", "bposd"): 14000, ("gross", "cur_par_unp", "bposd"): 6000,
    ("bb90", "cur_cz", "bposd"): 1500, ("bb90", "cur_par", "bposd"): 2500, ("bb90", "cur_slow", "bposd"): 2500,
    ("bb90", "proj_t2par", "bposd"): 6000, ("bb90", "cur_par_unp", "bposd"): 2500,
}
MAIN = ("cur", "proj", "curx0.5")


def circuits(fam, model):
    return FAM[fam] if model in MAIN else SENS_FAM[fam]


def blocks():
    for (fam, model, dec), A in ALLOW.items():
        yield fam, model, dec, A, circuits(fam, model)


assert sum(ALLOW.values()) == 139000
