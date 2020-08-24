#!/usr/bin/env python 
# -*- coding: utf-8 -*- 

import sys,os,re,io
import shutil, fileinput 
import glob, itertools 
import subprocess 
import argparse
import multiprocessing as mp
from multiprocessing import Process, Manager 
from functools import partial 
from sys import __stdout__
from epinano_modules import * 
import dask
import dask.dataframe as dd 
import pandas as pd 

#~~~~~~~~~~~~~~~~~~~~ private function ~~~~~~~~
# func1 subprocess call linux cmmands 
def file_exist (file):
	return os.path.exists (file)
	
def _rm (file):
	os.remove (file)
	
def stdin_stdout_gen (stdin_stdout):
	'''
	generator for subprocess popen stdout 
	'''
	for l in stdin_stdout:
		if isinstance (l,bytes):
			yield (l.decode('utf-8'))
			#sys.stderr.write (l.decode('utf-8')+'\n')
		else:
			yield l 
			#sys.stderr.write (l+'\n')	
	
def print_from_stdout (stdout_lst, outputfh):
	for i, o in enumerate (stdout_lst):
		for l in o: 
			if l.decode().startswith ('#'):
				if i >1 :
					continue
			outputfh.write(l.decode())		   
#~~~~~~~

def reads_mapping (reads_file, reference_file, ncpus, dtype):
	'''
	dtype: can be t[ranscriptome] or g[enome]
	'''
	dtype = dtype.lower()
	cmd_map = ''
	if args.type.startswith ("t"):
		cmd_map = f"minimap2 -ax map-ont -t {ncpus} -k 5 --MD " \
						f"{reference_file} {reads_file}|samtools view -hSb  - " \
						f"| samtools sort -@ {ncpus} - {reads_file}" 
	else:
		cmd_map = f"minimap2 -ax splice -uf -k14 -t {n_cpus} --MD " \
							f"{args.reference} {reads_file}|samtools view -hSb - " \
							f"| samtools sort -@ {args.threads} - {reads_file}" 
	return  cmd_map 
	

def _bam_to_tsv (bam_file,  reference_file, sam2tsv, type):
	'''
	type: reference types,i.e., trans or genome 
	'''
	
	awk_forward_strand = """ awk '{if (/^#/) print $0"\tSTARAND"; else print $0"\t+"}' """
	awk_reverse_strand = """ awk '{if (/^#/) print $0"\tSTARAND"; else print $0"\t-"}' """
	cmds = []

	if type.lower().startswith ("t"):	
		cmd =  f"samtools view -h -F 3860 {bam_file} | java -jar  {sam2tsv} -r {reference_file} "\
			f" | {awk_forward_strand}"		
		#subprocess_cmd (cmd)
		cmds = [cmd]
	else:
		cmd1 = (f"samtools view -h -F 3860 {bam_file} | java -jar  {sam2tsv} -r {reference_file} "
					f"| {awk_forward_strand} ")
		cmd2 = (f"samtools view -h -f 16 -F 3844 {bam_file} | java -jar  {sam2tsv} -r {reference_file} "
					f" | {awk_reverse_strand}")	
		cmds = [cmd1,cmd2]
	return cmds 
# data frame 

def df_is_not_empty(df):
	'''
	input df is a df filtred on reference id 
	if is is empty: next (df.iterrows()) does not work
	otherwise it returns a row of df 
	'''
	try:
		next (df.iterrows())
		return True
	except:
		return False
	
def df_proc (small_files_dir, outprefix):
	
	plusout = outprefix+'.plus_strand.per.site.var.csv'
	minusout = outprefix+'.minus_strand.per.site.var.csv'
	#outfh.write(header)
	#custom_sum = dd.Aggregation('custom_sum', lambda x: x.agg (":".join(str(x))), lambda x0: x0.agg(":".join(str(x0))))
	df = dd.read_csv ("{}/small_*.freq".format(small_files_dir)) 
	df_plus = df[df['strand'] == '+']
	df_minus = df[df['strand'] == '-']
	
	outs = [] 
	if df_is_not_empty (df_plus):
		df_groupy (df_plus, plusout)
		outs.append (plusout)
	if df_is_not_empty (df_minus):
		df_groupy(df_minus, minusout)
		outs.append (minusout)
	return outs 

def df_groupy(df, out):
	outfh = open (out,'w')
	header = "#Ref,pos,base,strand,cov,q_mean,q_median,q_std,mis,ins,del"
	print (header, file = outfh)
	gb = df.groupby(['#Ref','pos','base','strand']).agg({
               'cov':['sum'],
               'mis':['sum'],
               'ins':['sum'],
               'del':['sum'],
               'qual':['sum']})
	gb.reset_index()
	for i,j in gb.iterrows():
		i = ",".join (map (str, list(i)))
		cov = j['cov'].values[0]
		mis = '%0.5f' % (j['mis'].values[0]/cov)
		ins = '%0.5f' % (j['ins'].values[0]/cov)
		_de = '%0.5f' % (j['del'].values[0]/cov)
		q = np.array (j['qual'].str.split(':').values[0][:-1]).astype(int)  #quality sting ends with ':'
		qmn,qme,qst = '%0.5f' % np.mean(q), '%0.5f' % np.median(q), '%0.5f' % np.std(q)
		outfh.write ("{},{},{},{},{},{},{},{}\n".format(i,cov,qmn,qme,qst,mis,ins,_de))
	outfh.close()

#~~~~~~~~~~~~~~~~~~~~~~~ main () ~~~~~~~~~~~~~~~~~~~~~~~
parser = argparse.ArgumentParser()
parser.add_argument ('-r','--reads',help='fastq(a) reads input')
parser.add_argument ('-R','--reference', help='samtools faidx indexed reference file')
parser.add_argument ('-b', '--bam', type=str, help='bam file; if given; no need to offer reads file; mapping will be skipped')
parser.add_argument ('-f','--file', type=str, help='tsv file generated by sam2tsv.jar; if given, reads mapping and sam2tsv conversion will be skipped')
parser.add_argument ('-t', '--threads', type=int, default=4,  help='number of threads') 
parser.add_argument ('-s', '--sam2tsv',type=str, default='',help='/path/to/sam2tsv.jar; needed unless a sam2tsv.jar produced file is already given')
parser.add_argument ('-T', '--type', type=str, default="t" ,help="reference types, which is either g(enome) or t(ranscriptome);")
parser.add_argument ('-p','--per_read_variants', action='store_true', help='compute per reads variants statistics')
args=parser.parse_args()
#~~~~~~~~~~~~~~~~~~~~~~~ prepare for analysis ~~~~~~~~~~~~~~ 
tsv_gen = None  # generator 
prefix = '' 
#args.reads +'.per_site.var.csv'
def _tsv_gen ():
	if not args.file:
		if args.bam:
			bam_file = args.bam 
			if not file_exist (bam_file):
				sys.stderr.write (bam_file+' does not exist; pease double check!\n')
				exit()
			else:
				if not file_exist (args.sam2tsv):
					sys.stderr.write (" can  not find {} java program\n".format(args.sam2tsv))
					exit()
				if not os.path.exists (bam_file+'.bai'):
					os.system ('samtools index ' + bam_file + '.bai')
				if not args.reference :
					sys.stderr.write('requires reference file that was used for reads mapping\n')
					exit()
				if not file_exist (args.reference):
					sys.stderr.write('requires reference file does not exist\n')
					exit()
				prefix = bam_file.replace('.bam','')
				cmds = _bam_to_tsv (bam_file, args.reference, args.sam2tsv, args.type)
				if args.type[0].lower() == 't': #mappign to transcriptome; only one sam2tsv.jar command 
					cmd = subprocess.Popen ((cmds[0]),  stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True )
					tsv_gen = stdin_stdout_gen (cmd.stdout)
				elif args.type[0].lower() == 'g': #mapping to genome; sam2tsv.jar caled twice for + and - strands 
					cmd1 = subprocess.Popen ((cmds[0]), stdout=subprocess.PIPE, stderr = subprocess.PIPE,shell=True)
					cmd2 = subprocess.Popen ((cmds[1]), stdout=subprocess.PIPE, stderr = subprocess.PIPE,shell=True)
					tsv_gen = itertools.chain (stdin_stdout_gen (cmd1.stdout), stdin_stdout_gen (cmd2.stdout))
		else:
			if args.reads and args.reference:
				bam_file = args.reads + '.bam'
				prefix = args.reads 
				#~~~~~~~~~~~~~ minimap2 mapping commands ~~~~~~~~~~~~~~~~~~~~~~~~~
				cmd_map = reads_mapping (args.reads, args.reference, args.threads, args.type)
				sys.stderr.write ("++++ mapping command: \n")
				sys.stderr.write (cmd_map)
				proc = subprocess.Popen ((cmd_map), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
				o, e = proc.communicate ()
				if (proc.returncode):
					sys.stderr.write ('++++ mapping is UNsuccessful:\n')
					sys.stderr.write ('!!!! '+str(e)+'\n')
				else:
					sys.stderr.write ('++++ mapping is Successful\n')
					os.system ('samtools index ' + args.reads+'.bam')
					sys.stderr.write ('+++convert bam to tsv\n')
					cmds = 	_bam_to_tsv (bam_file, args.reference, args.sam2tsv, args.type)
				if args.type[0].lower() == 't': #mappign to transcriptome; only one sam2tsv.jar command 
					cmd = subprocess.Popen ((cmds[0]),  stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True )
					tsv_gen = stdin_stdout_gen (cmd.stdout)
				elif args.type[0].lower() == 'g': #mapping to genome; sam2tsv.jar caled twice for + and - strands 
					cmd1 = subprocess.Popen ((cmds[0]), stdout=cmd3.stdin, stderr = subprocess.PIPE,shell=True)
					cmd2 = subprocess.Popen ((cmds[1]), stdout=cmd3.stdin, stderr = subprocess.PIPE,shell=True)
					tsv_gen = itertools.chain (stdin_stdout_gen (cmd1.stdout), stdin_stdout_gen (cmd2.stdout))
			else:
				if not file_exist (args.reads):
					sys.stderr.write('please supply reads file\n')
				elif not file_exist (args.reference):
					sys.stderr.write('please supply reference file\n')
				exit()
	else:
		if  args.file:
			tsv_file = args.file 
			prefix = tsv_file.replace ('.tsv','')
			if os.path.exists (args.file):
				fh = openfile (tsv_file)
				firstline = fh.readline()
				fh.close()
				if len (firstline.rstrip().split()) != 10:
					sys.stderr.write('tsv file is not in right format!')
					sys.stderr.write('tsv files should contain these columns {}\n'.format("#READ_NAME     FLAG    CHROM   READ_POS        BASE    QUAL    REF_POS REF     OP      STARAND"))
				sys.stderr.write (tsv_file + ' already exists; will skip reads mapping and sam2tsv conversion \n')			
				tsv_gen = openfile (tsv_file)
			else:
				sys.stderr.write (tsv_file + ' does not exist; please double check \n')
				exit()
	return tsv_gen, prefix 
#~~~~~~~~~~~~~~~~  SAM2TSV ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
################# funciton run commands ########################### 
#~~~~~~~~~~~~~~~~ split tsv  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
tsv_gen, prefix = _tsv_gen()
tmp_dir = prefix + '.tmp_splitted'
if  os.path.exists(tmp_dir):
	shutil.rmtree (tmp_dir)
	sys.stderr.write ("{} already exists, will overwrite it\n".format(tmp_dir))
os.mkdir (tmp_dir)

number_threads = args.threads 
manager = Manager()
q = manager.Queue(args.threads)
#~~~~~~~~~~~~~~~~ compute per site variants frequecies ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#1 calculate variants frequency for each small splitted file 
processes = []
ps = Process (target = split_tsv_for_per_site_var_freq, args = (tsv_gen, q, number_threads, 4000))
processes.append (ps)

for _ in range(number_threads):
	ps = Process (target= tsv_to_freq_multiprocessing_with_manager, args = (q, tmp_dir))
	processes.append (ps) 
for ps in processes:
	ps.daemon = True
	ps.start()
for ps in processes:
	ps.join()

#2 combine small files and produce varinats frequencies per ref-position
#persite_var = prefix +'.per_site.var.csv'
var_files = df_proc (tmp_dir, prefix)

if  os.path.exists(tmp_dir):
	pool = mp.Pool(args.threads)
	tmp_files = glob.glob("{}/small*".format(tmp_dir))
	pool.map(_rm,  tmp_files)
	shutil.rmtree(tmp_dir)

#3 sliding window per site variants --> for making predicitons 
if len (var_files) == 1:
	slide_per_site_var(var_files[0])
elif len (var_files) == 2:
	pool = mp.Pool(2)
	pool.map(slide_per_site_var, var_files)
	pool.close(); pool.join()


# per read variants 
if args.per_read_variants:
	tsv_gen, prefix =_tsv_gen()
	outfile = prefix + ".per.read.var.csv"
	outfh = open (outfile, 'w')
	outfh.write ("#REF,REF_POS,REF_BASE,STRAND,READ_NAME,READ_POSITION,READ_BASE,BASE_QUALITY,MISMATCH,INSERTION,DELETION" + '\n')
	outfh.close()
	per_read_var = outfile 
	processes = []
	q = manager.Queue(100)
	ps = Process (target = split_tsv_for_per_read_var, args = (tsv_gen, q, args.threads))
	ps.start()
	processes.append (ps)
	for _ in range (args.threads):
		ps = Process (target = per_read_var_multiprocessing, args= (q, args.threads, outfile))
		processes.append (ps)
		ps.start()
	for ps in processes:
		ps.join()
	outfh.close()
	# slide per read var
	output = prefix + ".per_read_var.5mer.csv"
	outfh = open (output,'w')
	outfh.write("#Read,Read_Window,ReadKmer,Ref,RefKmer,Strand,Ref_Window,q1,q2,q3,q4,q5,mis1,mis2,mis3,mis4,mis5,ins1,ins2,ins3,ins4,ins5,del1,del2,del3,del4,del5\n")
	outfh.close()
	q = manager.Queue()
	ps = Process (target = split_reads_for_per_read_var_sliding , args = (per_read_var,q,number_threads))
	ps.start()
	for _ in range (number_threads):
		ps = Process (target = slide_per_read_var_multiprocessing, args = (q, output))
		processes.append (ps)
		ps.start()
	for ps in processes:
		ps.join()
	outfh.close()
exit()	

# finally remove tmp files 
#4