import re
import pandas as pd

from config import Config


class Dataset(Config):
    """

    Attributes
    ----------

    ukbb_vars: list
        Variable names based on user selections as coded in the Biobank.
    
    recoded_vars: list
        Variable names based on user selections as will be recoded.
    
    df: DataFrame
        Dataset which can be manipulated using the below methods

    Methods
    -------

    create_binary_variables(voi: str, patterns: dict)
        Takes as input a variable of interest (e.g., 'medication') and a dictionary with keys representing new
        variable names mapped onto regular expressions. New binary variables will be created based on whether
        each individual has a value matching the regular expression in any of the columns related to the variable
        of interest.

        Example:
        >>> myDataset.create_binary_variables("medication", {"taking_painkiller": "(aspirin|tylenol)"})
           
    recode_diagnoses()
        Creates new variables for groups of diagnoses included or excluded, based on
        whether one or more of such diagnoses is present.

    apply_inclusion_criteria(method: str)
        Apply inclusion criteria based on specified method. Available options are "AND" and "OR".
    
    apply_exclusion_criteria()
        Apply exclusion criteria by removing cases where any of the specified diagnoses are present

    clean(voi: str)
        Takes as input a variable of interest (e.g., 'medication'). Removes all columns beginning with this string from the final dataframe.
    
    recode_vars()
        Replace values for each variable as specified in the config class 
    
    write_csv()
        Write self.df to the filepath specified in the config class 

    """

    ukbb_vars, recoded_vars = ["eid"], ["eid"]
    for var in Config.variables:
        if Config.variables[var]["Included"]:
            array_vars = []
            for i in Config.variables[var]['ArrayRange']:
               array_vars.append(f"{Config.variables[var]['DataField']}-{Config.variables[var]['InstanceNum']}.{i}")
            ukbb_vars += array_vars
            if len(Config.variables[var]['ArrayRange']) == 1:
                recoded_vars.append(f"{var}_t{Config.variables[var]['InstanceNum']}")
            else:
                array_vars = []
                for i in Config.variables[var]['ArrayRange']:
                    array_vars.append(f"{var}_t{Config.variables[var]['InstanceNum']}_{i}")
                recoded_vars += array_vars
    assert len(ukbb_vars) == len(recoded_vars)

    def __init__(self) -> None:
        self.df = pd.read_csv(self.filepaths["RawData"], dtype=str, usecols=self.ukbb_vars)
        self.df.rename({k: v for k, v in zip(self.ukbb_vars, self.recoded_vars)}, axis=1, inplace=True)
        self.df.dropna(axis=1, how="all", inplace=True)
    
    def create_binary_variables(self, voi: str, patterns: dict):

        cols = [col for col in self.df if col.startswith(voi)]
        all_vars = list(patterns.keys())
        new_vars = {var_name: [] for var_name in ["eid"] + all_vars}

        for index, row in self.df[cols].iterrows():
            new_vars["eid"].append(self.df["eid"][index])
            for pat in patterns:
                for value in row:
                    try:
                        if re.match(patterns[pat], value) is not None:
                            new_vars[pat].append(True)
                            break
                    except TypeError:
                        continue
                if len(new_vars["eid"]) != len(new_vars[pat]):
                    new_vars[pat].append(False)

        if not sum([len(x) for x in new_vars.values()]) == len(new_vars["eid"]) * len(new_vars.keys()):
            raise ValueError(f"{sum([len(x) for x in new_vars.values()])} != {len(new_vars['eid']) * len(new_vars.keys())}")
        
        new_df = pd.DataFrame(new_vars)
        self.df = pd.merge(self.df, new_df, left_on="eid", right_on="eid")

    def recode_diagnoses(self):
        dx_cols = [col for col in self.df if col.startswith("diagnoses")]
        all_dx = list(self.selected_diagnoses.keys())
        new_vars = {var_name: [] for var_name in ["eid"] + all_dx}

        for i in range(len(self.df)):
            new_vars["eid"].append(self.df["eid"][i])
            for col in dx_cols:
                value = self.df[col][i]
                if pd.isnull(value):
                    for dx in all_dx:
                        if len(new_vars[dx]) != len(new_vars["eid"]):
                            new_vars[dx].append(False)
                    break
                for dx in self.selected_diagnoses:
                    if re.match(self.selected_diagnoses[dx], value) is not None:
                        if len(new_vars[dx]) != len(new_vars["eid"]):
                            new_vars[dx].append(True)

        assert sum([len(x) for x in new_vars.values()]) == len(new_vars["eid"]) * len(new_vars.keys())

        new_df = pd.DataFrame(new_vars)
        self.df = pd.merge(self.df, new_df, left_on="eid", right_on="eid")
        self.df.drop(dx_cols, axis=1, inplace=True)

    def apply_inclusion_criteria(self, method: str):
        if method == "AND":
            for key in self.included_diagnoses:
                self.df = self.df[self.df[key] == True]
        elif method == "OR":
            list_series = [self.df[key] == True for key in self.included_diagnoses]
            included = pd.concat(list_series, axis=1).any(axis=1)
            self.df = self.df[included]
        else:
            raise ValueError("Available methods: 'AND', 'OR'")

    def apply_exclusion_criteria(self):
        for key in self.excluded_diagnoses:
            self.df = self.df[self.df[key] == False]

    def clean(self, voi: str):
        colsToDrop = [col for col in self.df if col.startswith(voi)]
        self.df.drop(colsToDrop, axis=1, inplace=True)
            
    def recode_vars(self):
        for name in self.variables:
            cols = [col for col in self.df.columns if col.startswith(name)]
            if self.variables[name]["Included"] and cols != []:
                self.df[cols] = self.df[cols].replace(to_replace=self.variables[name]["Coding"])

    def write_csv(self):
        self.df.to_csv(self.filepaths["Output"], index=False)
