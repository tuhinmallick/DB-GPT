def csv_colunm_foramt(val):
    if "$" in str(val):
        return float(val.replace("$", "").replace(",", ""))
    return float(val.replace("¥", "").replace(",", "")) if "¥" in str(val) else val
