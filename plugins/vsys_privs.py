"""
vsys sub-configurator.  Maintains configuration parameters associated with vsys scripts.
All slice attributes with the prefix vsys_ are written into configuration files on the
node for the reference of vsys scripts.
"""

import logger
import os

VSYS_PRIV_DIR = "/etc/planetlab/vsys-attributes"

def start():
    logger.log("vsys_privs: plugin starting")
    if (not os.path.exists(VSYS_PRIV_DIR)):
        os.makedirs(VSYS_PRIV_DIR)
        logger.log("vsys_privs: Created vsys attributes dir")

def GetSlivers(data, config=None, plc=None):

    if 'slivers' not in data:
        logger.log_missing_data("vsys_privs.GetSlivers", 'slivers')
        return


    privs = {}

    # Parse attributes and update dict of scripts
    if 'slivers' not in data:
        logger.log_missing_data("vsys_privs.GetSlivers", 'slivers')
        return
    for sliver in data['slivers']:
        slice = sliver['name']
        for attribute in sliver['attributes']:
            tag = attribute['tagname']
            value = attribute['value']
            if tag.startswith('vsys_'):
                if (slice in privs):
                    slice_priv = privs[slice]
                    if (tag in slice_priv):
                        slice_priv[tag].append(value)
                    else:
                        slice_priv[tag]=[value]

                    privs[slice] = slice_priv
                else:
                    privs[slice] = {tag:[value]}

    cur_privs = read_privs()
    write_privs(cur_privs, privs)

def read_privs():
    cur_privs={}
    priv_finder = os.walk(VSYS_PRIV_DIR)
    priv_find = [i for i in priv_finder]
    (rootdir, slices, foo) = priv_find[0]

    for slice in slices:
        cur_privs[slice]={}

    if (len(priv_find)>1):
        for (slicedir, bar, tagnames) in priv_find[1:]:
            if (bar != []):
                # The depth of the vsys-privileges directory = 1
                pass

            for tagname in tagnames:
                tagfilename = os.path.join(slicedir, tagname)
                with open(tagfilename) as tagfile:
                    values_n = tagfile.readlines()
                    values = [ v.rstrip() for v in values_n ]
                    slice = os.path.basename(slicedir)
                    cur_privs[slice][tagname] = values

    return cur_privs

def write_privs(cur_privs, privs):
    for slice in list(privs.keys()):
        variables = privs[slice]
        slice_dir = os.path.join(VSYS_PRIV_DIR, slice)
        if (not os.path.exists(slice_dir)):
            os.mkdir(slice_dir)

        # Add values that do not exist
        for k in list(variables.keys()):
            v = variables[k]
            if (slice in cur_privs
                    and k in cur_privs[slice]
                    and cur_privs[slice][k] == v):
                # The binding has not changed
                pass
            else:
                v_file = os.path.join(slice_dir, k)
                f = open(v_file, 'w')
                data = '\n'.join(v)
                f.write(data)
                f.close()
                logger.log("vsys_privs: added vsys attribute %s for %s"%(k, slice))

    # Remove files and directories
    # that are invalid
    for slice in list(cur_privs.keys()):
        variables = cur_privs[slice]
        slice_dir = os.path.join(VSYS_PRIV_DIR, slice)

        # Add values that do not exist
        for k in list(variables.keys()):
            if (slice in privs
                    and k in cur_privs[slice]):
                # ok, spare this tag
                print("Sparing  %s, %s "%(slice, k))
            else:
                v_file = os.path.join(slice_dir, k)
                os.remove(v_file)

        if (slice not in privs):
            os.rmdir(slice_dir)


if __name__ == "__main__":
    test_slivers = {'slivers':[
        {'name':'foo', 'attributes':[
            {'tagname':'vsys_m', 'value':'2'},
            {'tagname':'vsys_m', 'value':'3'},
            {'tagname':'vsys_m', 'value':'4'}
            ]},
        {'name':'bar', 'attributes':[
            #{'tagname':'vsys_x', 'value':'z'}
            ]}
        ]}
    start(None, None)
    GetSlivers(test_slivers)
