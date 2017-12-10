from Util.db_util import *
import numpy as np
import matplotlib.pyplot as plt
from pylab import *
import seaborn as sns
sns.set()

def select_time_range_to_dataframe(cursor, site_id, resource_list):
    df_final = pd.DataFrame()
    feq = '21:00'
    for id in resource_list:
        query = "select time, value from site_" + site_id + " where id = " + str(id) + \
                " and time LIKE  '%" + feq + "%';"
        resp = cursor.execute(query)
        df = pd.DataFrame(resp.fetchall(), columns=["timestamps", id], dtype=float)
        df = df.reset_index(drop=True)
        df = df.set_index('timestamps')
        df = df[~df.index.duplicated(keep='first')]
        df_final = pd.concat([df_final, df], axis=1)
    return df_final


def ETL_activity(df):
    """
    if any none zero data from any sensor, this device is active
    so we add all up from one device and more accuracy for activity statistic

    :param df: data from the same device, different sensors
    :return: the device on the timeline  active or not (1 or 0)
    """
    df = df[~df.index.duplicated(keep='first')]
    df[df > 0] = 1
    df_active = df.sum(axis=1)
    df_active[df_active > 0] = 1
    return df_active


def query_device(c, site_id):
    """
    query {device : resource list} from same site
    :param c: cursor of database
    :param site_id: site id
    :return: dictionary list
    """
    device_dict = defaultdict(list)
    query = "select site,resource,uri from details_sensor " \
            "where uri not like 'site%' and subsite=0 and site =" + str(site_id)
    resp = c.execute(query).fetchall()

    # find device
    for site, resource,uri in resp:
        if '0x' in uri:
            for i in uri.split('/'):
                if '0x' in i:
                    index = (uri.split('/').index(i))
                    device = uri.split("/")[index]
                    break
            device_dict[device].append(resource)
        elif 'soderhamn' in uri or 'gaia-ea' in uri:
            device = uri.split("/")[1]
            device_dict[device].append(resource)
        elif 'sapienza' in uri or 'gaia-prato' in uri:
            device = uri.split("/")[2]
            device_dict[device].append(resource)
        else:
            device = uri.split("/")[0]
            device_dict[device].append(resource)
    return device_dict


def reindex_df(day_index, df):
    # reset index of the dataframe
    df['timestamps'] = day_index
    df = df.reset_index(drop=True)
    df = df.set_index('timestamps')
    return df

if __name__ == "__main__":
    # retrieve data from database
    database = '/Users/nanazhu/Documents/Sapienza/Thesis/src_python/test.db'
    with create_connection(database) as conn:
        try:
            c = conn.cursor()
            site_list = [str(id[0]) for id in c.execute("select site from details_sensor group by site;")]
            # site_list = [  # '144243', '155865',
            #     "144024", "28843", "144243", "28850",
            #     #              # '157185',#"155849", #"144242",  "19640", "27827", "155849",
            #     #              #     "155851", "155076", "155865", "155077",
            #     #              #     "155877", "157185", "159705"
            # ]
            if len(site_list) <= 1:
                print("site list need more than 1 ", site_list)

            df_device_env = pd.DataFrame()
            df_device_syn = pd.DataFrame()
            df_device_lib = pd.DataFrame()
            df_device_pow = pd.DataFrame()
            for site_id in site_list:
                print(site_id,".......")
                # query database:  {device:[resources list],...}
                device_dict = query_device(c,site_id)

                # device : list of sensors , check activity
                for device in device_dict:
                    # print("Checking data from :",device, device_dict[device])
                    df_device = select_time_range_to_dataframe(c, site_id, device_dict[device])
                    df_device = df_device.sort_index()
                    df_static = ETL_activity(df_device)
                    # category different types into different dataframe
                    if 'libelium' in device:
                        df_device_lib[str(site_id) + device] = df_static.values
                    elif 'synfield' in device:
                        df_device_syn[str(site_id) + device] = df_static.values
                    else:
                        query = "select property from details_sensor where resource = " + str(device_dict[device][0])
                        if 'Power' in c.execute(query).fetchall()[0][0] or 'Current' in c.execute(query).fetchall()[0][
                            0]:
                            df_device_pow[str(site_id) + device] = df_static.values
                        else:
                            print(df_device_env.shape,"\t",df_static.shape)
                            df_device_env[str(site_id) + device] = df_static.values

            # reset index with plot Year - Month as label
            day_index = [pd.to_datetime(str(date)).strftime('%Y-%m') for date in df_static.index.values]
            df_device_syn = reindex_df(day_index, df_device_syn)
            df_device_lib = reindex_df(day_index, df_device_lib)
            df_device_pow = reindex_df(day_index, df_device_pow)
            df_device_env = reindex_df(day_index, df_device_env)

            ylabel_list = ["Env", "Syn", "Lib", "Pow"]
            df_list = [df_device_env, df_device_syn, df_device_lib, df_device_pow]
            fig, axn = plt.subplots(4, 1, sharex=True)
            for j, ax in enumerate(axn.flat):
                # plot the heatmap for each type
                sns.heatmap(df_list[j].T,
                            ax=ax,
                            xticklabels=31,
                            yticklabels=False,
                            cbar=False
                            )
                ax.set_xlabel('')
                ax.set_ylabel(ylabel_list[j])# , rotation=90, labelpad=5, fontsize=9)
            axn[-1].set_xticklabels(sorted(set(day_index)))
            plt.show()
        except Error as e:
            print("SQL ERROR:", e)