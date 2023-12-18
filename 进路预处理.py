# -*- coding: utf-8 -*-
"""
Created on Sat Dec  9 14:52:27 2023

@author: Duan Chuyu
"""

import pandas as pd
import re

# 处理点和边
edges = pd.read_excel('edges.xlsx')
points = pd.read_excel('points.xlsx')

# 确保数据合法，避免偶然输入的空格，并让绝缘节为 西-东 格式
xDict = dict(zip(points['point'].apply(lambda i : str(i)),points['point_X']))
yDict = dict(zip(points['point'].apply(lambda i : str(i)),points['point_Y']))

def stringProcess(s):
    s = str(s).strip()
    if(s.find('-') == -1):
        return s
    s1, s2 = sorted(s.split('-'), key = lambda p : xDict[p])
    return '{}-{}'.format(s1,s2)
points['point'] = points['point'].apply(lambda i : stringProcess(i)) 
points = points.set_index('point')
edges['from'] = edges['from'].apply(lambda i : stringProcess(i)) 
edges['to'] = edges['to'].apply(lambda i : stringProcess(i)) 

points.to_excel('points_processed.xlsx')
edges.to_excel('edges_processed.xlsx')

# 读取进路
routes = pd.read_excel('routes.xlsx')
routes = routes.set_index('id')
routes['station_yard'] = routes['route']
routes['route_type'] = routes['route']
routes['start_line'] = routes['route']
routes['end_line'] = routes['route']
routes['start_point'] = routes['route']
routes['end_point'] = routes['route']
routes['XZ'] = routes['route']
routes['YZ'] = routes['route']

for index, row in routes.iterrows():
    route = row['route'] #获取进路字符串
    start, end, typ = None, None, None
    p = re.compile(r'.*?(?=G)')
    gudao = p.match(route).group()
    
    if(route.find('东向') >= 0):
        if(route.find('接车') >= 0):
            start = 'S'
            end = 'S' + gudao
            typ = '接车进路'
            if(route.find('宁杭') >= 0):
                start = 'SH'
        if(route.find('发车') >= 0):
            start = 'X' + gudao
            end = 'SN'
            typ = '发车进路'
            if(route.find('宁杭') >= 0):
                end = 'SHN'
    if(route.find('西向') >= 0):
        if(route.find('接车') >= 0):
            start = 'X'
            end = 'X' + gudao
            typ = '接车进路'
            if(route.find('动车A线') >= 0):
                start = 'XDA'
            if(route.find('动车B线') >= 0):
                start = 'XDB'
        if(route.find('发车') >= 0):
            start = 'S' + gudao 
            end = 'XN' 
            typ = '发车进路'
            if(route.find('动车A线') >= 0):
                end = 'XDA'
            if(route.find('动车B线') >= 0):
                end = 'XDB'
    row['start_point'] = start
    row['end_point'] = end
    row['route_type'] = typ
    
    row['XZ'] = 0
    row['YZ'] = 0
    if(route.find('东向') >= 0):
        if(route.find('发车') >= 0):
            row['XZ'] = points.loc[start, 'point_X'] - 500
            row['YZ'] = points.loc[start, 'point_Y'] 
    if(route.find('西向') >= 0):
        if(route.find('发车') >= 0):
            row['XZ'] = points.loc[start, 'point_X'] + 500
            row['YZ'] = points.loc[start, 'point_Y'] 
    
    row['station_yard'] = '京沪场'
        
    line = {'S':'京沪上行上海端', 'SH':'京沪宁杭联上行杭州端', 
            'SHN':'京沪宁杭联下行杭州端','X':'京沪下行北京端',
            'XN':'京沪上行北京端','XDA':'动车A线', 'XDB':'动车B线', 
            'SN':'京沪上行上海端'}
    if(start in line):
        row['start_line'] = line[start]
    else:
        row['start_line'] = gudao + 'G'
    if(end in line):
        row['end_line'] = line[end]
    else:
        row['end_line'] = gudao + 'G'
routes.to_excel('routes_processed.xlsx')