#!/usr/bin/env python
# coding:utf8

import time
import sys
reload(sys)
sys.setdefaultencoding( "utf8" )
from flask import *
import warnings
warnings.filterwarnings("ignore")
import MySQLdb
import MySQLdb.cursors
import numpy as np
from config import *
import pprint
import random
import math
import jieba
import jieba.analyse
import jieba.posseg as pseg
import re

app = Flask(__name__)
app.config.from_object(__name__)

# 连接数据库
def connectdb():
	db = MySQLdb.connect(host=HOST, user=USER, passwd=PASSWORD, db=DATABASE, port=PORT, charset=CHARSET, cursorclass = MySQLdb.cursors.DictCursor)
	db.autocommit(True)
	cursor = db.cursor()
	return (db,cursor)

# 关闭数据库
def closedb(db,cursor):
	db.close()
	cursor.close()

def compare(li, post, key=''):
	dist = []
	for item in li:
		if not key == '':
			tmp = item[key].replace(' ', '')
		else:
			tmp = item[0].replace(' ', '')
		if tmp == '':
			dist.append([0.0, item])
			continue
		total = 0.0
		same = 0.0
		for i in xrange(0, len(post)):
			for j in xrange(0, len(tmp)):
				total += 1
				if post[i] == tmp[j]:
					same += 1
		dist.append([same / total, item])
	dist.sort(key=lambda x:x[0], reverse=True)

	return dist[0][1] 

# 首页
@app.route('/')
def index():
	return render_template('index.html')

# 检测模式
@app.route('/mode', methods=['POST'])
def mode():
	(db, cursor) = connectdb()
	cursor.execute("select * from keywords")
	keywords = cursor.fetchall()
	closedb(db, cursor)
	tmp = {}
	for k in keywords:
		tmp[k['keyword']] = k['weight']
	keywords = tmp

	data = request.form
	post = data['post']

	query = False
	qs = ['谁', '何', '什么', '哪', '几', '多少', '怎']
	for q in qs:
		if post.find(q) >= 0:
			query = True
			break

	post = jieba.cut(post)
	total = 0.0
	weight = 0.0
	for p in post:
		if p in [' ', '\t', '\n', '。', '，', '(', ')', '（', '）', '：', '□', '？', '！', '《', '》', '、', '；', '“', '”', '……']:
			continue
		total += 1
		if keywords.has_key(p):
			weight += keywords[p]

	return json.dumps({'post': data['post'], 'weight': weight / total, 'query': query})

# 输出对话
@app.route('/chat', methods=['POST'])
def chat():
	data = request.form
	post = data['post'].strip()
	submode = data['submode']
	(db, cursor) = connectdb()

	# 完全匹配
	cursor.execute("select * from pairs where post=%s", [post])
	response = cursor.fetchall()

	if len(response) > 0:
		closedb(db, cursor)
		response = compare(response, post, 'response')

		if response['category'] == '随便唠唠':
			submode = 0
		else:
			submode = 1

		return json.dumps({'post': post, 'submode': submode, 'response': response['response'].replace(' ', '')})
	else:
		# 模版匹配
		cursor.execute("select * from templates")
		templates = cursor.fetchall()
		for item in templates:
			reg = unicode(item['post'])
			reg = re.compile(reg)
			reg = list(set(reg.findall(post)))
			if len(reg) == 1 and float(len(reg[0])) / float(len(post)) >= 0.5:
				response = item['response'].split('^')
				closedb(db, cursor)
				return json.dumps({'post': post, 'submode': item['submode'], 'response': response[int(math.floor(random.random() * len(response)))]})

		# 查询法律
		cursor.execute("select * from laws")
		laws = cursor.fetchall()
		keywords = jieba.analyse.extract_tags(post, topK=3, withWeight=False, allowPOS=())
		for law in laws:
			flag = True
			for k in keywords:
				if law['content'].find(k) < 0:
					flag = False
					break
			if flag:
				content = law['content'].replace(' ', '').replace('\t', '').replace('\r', '\n').replace('。', '\n').split('\n')
				response = []
				for c in content:
					c = c.strip()
					if c == '':
						continue
					count = 0
					for k in keywords:
						if c.find(k) >= 0:
							count += 1
					response.append([c, count, len(c)])
				response.sort(key=lambda x:x[1], reverse=True)
				tmp = []
				for r in response:
					if r[1] == response[0][1]:
						tmp.append(r)
					else:
						break
				response = tmp
				closedb(db, cursor)

				response = compare(response, post)

				tmp = len(response) / len(post)

				if tmp > 5:
					continue

				else:
					return json.dumps({'post': post, 'submode': 2, 'response': response[0]})

		# 查询百科
		cursor.execute("select * from entries")
		entries = cursor.fetchall()
		query = False
		qs = ['谁', '何', '什么', '哪', '几', '多少', '怎']
		for q in qs:
			if post.find(q) >= 0:
				query = True
				break
		if query:
			words = pseg.cut(post)
			for word, flag in words:
				if flag in ['n', 'nr', 'nr1', 'nr2', 'nrj', 'nrf', 'ns', 'nsf', 'nt', 'nz']:
					for e in entries:
						if e['title'].find(word) >= 0:
							closedb(db, cursor)
							if e['photo'][:4] == 'http':
								return json.dumps({'post': post, 'submode': 2, 'response': e['title'] + ' ' + e['category'] + '<br/>' + e['definition'] + '<br/><img src="' + e['photo'] + '">'})
							else:
								return json.dumps({'post': post, 'submode': 2, 'response': e['title'] + ' ' + e['category'] + '<br/>' + e['definition']})


		# 关键词匹配
		tmp = jieba.analyse.extract_tags(post, topK=10, withWeight=False, allowPOS=())
		keywords = ''
		for p in tmp:
			if p in [' ', '\t', '\n', '。', '，', '(', ')', '（', '）', '：', '□', '？', '！', '《', '》', '、', '；', '“', '”', '……']:
				continue
			else:
				keywords = p
				break

		cursor.execute("select * from pairs where keywords=%s", [keywords])
		response = cursor.fetchall()
		closedb(db, cursor)

		if len(response) > 0:
			response = compare(response, post, 'response')

			if response['category'] == '随便唠唠':
				submode = 0
			else:
				submode = 1

			return json.dumps({'post': post, 'submode': submode, 'response': response['response'].replace(' ', '')})
		else:
			ans = ['真棒', '真不错', '好像很厉害的样子', '听起来好有意思', '给你点个赞', '给你打101分，多一分不怕你骄傲', '哦哦', '这样啊', '这……', '好吧', '好滴', '嗯嗯', '呵呵', '嘿嘿', '啊哈～']
			return json.dumps({'post': post, 'submode': 0, 'response': ans[int(math.floor(random.random() * len(ans)))]})

# 用户反馈
@app.route('/rank', methods=['POST'])
def rank():
	(db, cursor) = connectdb()
	data = request.form
	cursor.execute("insert into ranks(post, response, rank, timestamp) values(%s, %s, %s, %s)", [data['post'].strip(), data['response'].strip(), data['rank'], int(time.time())])
	closedb(db, cursor)
	return json.dumps({'post': data['post'], 'response': data['response'], 'rank': data['rank']})

if __name__ == '__main__':
	app.run(debug=True)