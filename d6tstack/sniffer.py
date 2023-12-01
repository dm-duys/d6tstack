#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

Finds CSV settings and Excel sheets in multiple files. Often needed as input for stacking

"""
import collections
import csv

import d6tcollect

# d6tcollect.init(__name__)

# ******************************************************************
# csv
# ******************************************************************


def csv_count_rows(fname, encoding="utf-8"):
    def blocks(files, size=65536):
        while True:
            b = files.read(size)
            if not b:
                break
            yield b

    with open(fname, encoding=encoding) as f:
        nrows = sum(bl.count("\n") for bl in blocks(f))

    return nrows


class CSVSniffer(object, metaclass=d6tcollect.Collect):
    """

    Automatically detects settings needed to read csv files. SINGLE file only, for MULTI file use CSVSnifferList

    Args:
        fname (string): file path
        nlines (int): number of lines to sample from each file
        delims (string): possible delimiters, default ",;\t|"

    """

    def __init__(self, fname, nlines=10, delims=",;\t|", encoding="utf-8"):
        self.cfg_fname = fname
        self.encoding = encoding
        self.nrows = csv_count_rows(
            fname, encoding
        )  # todo: check for file size, if large don't run this
        self.cfg_nlines = min(
            nlines, self.nrows
        )  # read_lines() doesn't check EOF # todo: check 1% of file up to a max
        self.cfg_delims_pool = delims
        self.delim = None  # delim used for the file
        self.csv_lines = None  # top n lines read from file
        self.csv_lines_delim = None  # detected delim for each line in file
        self.csv_lines_lineterm = None  # detected lineterm for each line in file
        self.csv_rows = None  # top n lines split usingn delim

    def read_nlines(self):
        # read top lines
        fhandle = open(self.cfg_fname, encoding=self.encoding)
        self.csv_lines = [fhandle.readline().rstrip() for _ in range(self.cfg_nlines)]
        fhandle.close()

    def scan_delim(self):
        if not self.csv_lines:
            self.read_nlines()

        # get delimiter for each line in file
        delims = []
        for line in self.csv_lines:
            try:
                csv_sniff = csv.Sniffer().sniff(line, self.cfg_delims_pool)
                delims.append(csv_sniff.delimiter)
            except:
                delims.append(None)  # todo: able to catch exception more specifically?

        self.csv_lines_delim = delims

    def scan_lineterm(self):
        if not self.csv_lines:
            self.read_nlines()

        # get delimiter for each line in file
        lineterm = []
        for line in self.csv_lines:
            try:
                csv_sniff = csv.Sniffer().sniff(line, self.delim)
                lineterm.append(csv_sniff.lineterminator)
            except Exception as e:
                print(e)
                lineterm.append(
                    None
                )  # todo: able to catch exception more specifically?

        self.csv_lines_lineterm = lineterm

    def get_lineterm(self):
        if not self.csv_lines_lineterm:
            self.scan_lineterm()

        # all line terminators the same?
        if len(set(self.csv_lines_lineterm)) > 1:
            self.lineterm_is_consistent = False
            csv_lineterm_count = collections.Counter(self.csv_lines_lineterm)
            csv_lineterm = csv_lineterm.most_common(1)[0][
                0
            ]  # use the most common used delimeter
            # todo: rerun on cfg_csv_scan_topline**2 files in case there is a large # of header rows
        else:
            self.lineterm_is_consistent = True
            csv_lineterm = self.csv_lines_lineterm[0]

        if csv_lineterm == None:
            raise IOError(
                "Could not determine a valid delimiter, pleaes check your files are .csv or .txt using one delimiter of %s"
                % (self.cfg_delims_pool)
            )
        else:
            self.lineterm = csv_lineterm
        return self.lineterm

    def get_delim(self):
        if not self.csv_lines_delim:
            self.scan_delim()

        # all delimiters the same?
        if len(set(self.csv_lines_delim)) > 1:
            self.delim_is_consistent = False
            csv_delim_count = collections.Counter(self.csv_lines_delim)
            csv_delim = csv_delim_count.most_common(1)[0][
                0
            ]  # use the most common used delimeter
            # todo: rerun on cfg_csv_scan_topline**2 files in case there is a large # of header rows
        else:
            self.delim_is_consistent = True
            csv_delim = self.csv_lines_delim[0]

        if csv_delim == None:
            raise IOError(
                "Could not determine a valid delimiter, pleaes check your files are .csv or .txt using one delimiter of %s"
                % (self.cfg_delims_pool)
            )
        else:
            self.delim = csv_delim

        self.csv_rows = [s.split(self.delim) for s in self.csv_lines][
            self.count_skiprows() :
        ]
        if self.check_column_length_consistent():
            self.certainty = "high"
        else:
            self.certainty = "probable"

        return self.delim

    def check_column_length_consistent(self):
        # check if all rows have the same length. NB: this is just on the sample!
        if not self.csv_rows:
            self.get_delim()

        return len(set([len(row) for row in self.csv_rows])) == 1

    def count_skiprows(self):
        # finds the number of rows to skip by finding the last line which doesn't use the selected delimiter
        if not self.delim:
            self.get_delim()

        if self.delim_is_consistent:  # all delims the same so nothing to skip
            return 0

        l = [d != self.delim for d in self.csv_lines_delim]
        l = list(reversed(l))
        return len(l) - l.index(True)

    def has_header_inverse(self):
        # checks if head present if all columns in first row contain a letter
        if not self.csv_rows:
            self.get_delim()

        def is_number(s):
            try:
                float(s)
                return True
            except ValueError:
                return False

        self.is_all_rows_number_col = all(
            [any([is_number(s) for s in row]) for row in self.csv_rows]
        )

        """
        self.row_distance = [distance.jaccard(self.csv_rows[0], self.csv_rows[i]) for i in range(1,len(self.csv_rows))]

        iqr_low, iqr_high = np.percentile(self.row_distance[1:], [5, 95])
        is_first_row_different = not(iqr_low <= self.row_distance[0] <= iqr_high)
        """

    def has_header(self):
        # more likely than not to contain headers so have to prove no header present
        self.has_header_inverse()
        return not self.is_all_rows_number_col


class CSVSnifferList(object, metaclass=d6tcollect.Collect):
    """

    Automatically detects settings needed to read csv files. MULTI file use

    Args:
        fname_list (list): file names, eg ['a.csv','b.csv']
        nlines (int): number of lines to sample from each file
        delims (string): possible delimiters, default ',;\t|'

    """

    def __init__(self, fname_list, nlines=10, delims=",;\t|", encoding="utf-8"):
        self.cfg_fname_list = fname_list
        self.sniffers = [
            CSVSniffer(fname, nlines, delims, encoding) for fname in fname_list
        ]

    def get_all(self, fun_name):
        val = {
            fun_name: [
                {sniffer.cfg_fname: getattr(sniffer, fun_name)()}
                for sniffer in self.sniffers
            ],
        }
        return val

    def sniff_all(self):
        results = {}
        for sniffer in self.sniffers:
            results[sniffer.cfg_fname] = {
                "delimiter": sniffer.get_delim(),
                "lineterminator": sniffer.get_lineterm(),
                "skiprows": sniffer.count_skiprows(),
                "has_header": sniffer.has_header(),
                "header": 0 if sniffer.has_header() else None,
            }
        return results

    def get_delim(self):
        return self.get_all("get_delim")

    def count_skiprows(self):
        return self.get_all("count_skiprows")

    def has_header(self):
        return self.get_all("has_header")

    def get_lineterm(self):
        return self.get_all("get_lineterm")


def sniff_settings_csv(fname_list, encoding="utf-8"):
    sniff = CSVSnifferList(fname_list, encoding=encoding)
    return sniff.sniff_all()
