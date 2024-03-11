import numpy as np
import cv2
import os
from PIL import Image,ImageEnhance
import torch
from super import superfeature
import cv2
import csv
import re
from Stitcher import Stitcher
import glob
from natsort import natsorted
import pyelastix
def imgnorm(img):
    #dst = cv2.pyrMeanShiftFiltering(img, 1, 10)
    img_float32 = np.float32(img)
    img_NORM_MINMAX = img_float32.copy()
    cv2.normalize(img_float32,img_NORM_MINMAX,0,255,cv2.NORM_MINMAX)
    img_norm=img_NORM_MINMAX.astype('uint8')
    return img_norm
def convert1(img):
    if len(img.shape)==2:
        imgrgb=cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
    else:
        imgrgb=img
    imgrgb[:,:,0]=0
    imgrgb[:,:,2]=0
    imgout=imgnorm(imgrgb)
    return imgout

def convert2(img):
    if len(img.shape)==2:
        imgrgb=cv2.cvtColor(img,cv2.COLOR_GRAY2BGR)
    else:
        imgrgb=img
    imgrgb[:,:,1]=0
    imgrgb[:,:,0]=0
    imgout=imgnorm(imgrgb)
    return imgout

def imggray(img):
    imGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    imGray=imGray.astype('uint8')
    return imGray



def siftPointAlignment(img,H,w):
    imgOut = cv2.warpPerspective(img, H, (img.shape[1]+2*w,img.shape[0]+2*w),flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    return imgOut

def warp(img,M,w):
    imgOut=cv2.warpAffine(img, M, (img.shape[1]+2*w,img.shape[0]+2*w))
    return imgOut
def csvhandle(csv,pad):
    csv['x']=csv['x']+pad
    csv['y']=csv['y']+pad
    return csv

def csvhandle2(csv):
    csv['x']=csv['x']
    csv['y']=csv['y']
    return csv

def csv_regi(csv,H):
    Hc=H.copy()
    Hc[0,2]=-Hc[0,2]
    Hc[1,2]=-Hc[1,2]
    for i in np.arange(csv.shape[0]):
        px=csv['x'].loc[i]
        py=csv['y'].loc[i]#读取一个点
        XY0 =np.array([[px],[py],[1]])#变换前坐标
        XYF=np.dot(Hc,XY0)
        pxf=XYF[0,0]
        pyf=XYF[1,0]
        csv['x'].loc[i]=pxf
        csv['y'].loc[i]=pyf
    return csv

def getGoodMatchPoint(mkpts0, mkpts1, confidence,  match_threshold:float=0.2):
    n = min(mkpts0.size(0), mkpts1.size(0))
    srcImage1_matchedKPs, srcImage2_matchedKPs=[],[]

    if (match_threshold > 1 or match_threshold < 0):
        print("match_threshold error!")

    for i in range(n):
        kp0 = mkpts0[i]
        kp1 = mkpts1[i]
    
        pt0=(kp0[0].item(),kp0[1].item())
        pt1=(kp1[0].item(),kp1[1].item())
        c = confidence[i].item()
        if (c > match_threshold):
            srcImage1_matchedKPs.append(pt0)
            srcImage2_matchedKPs.append(pt1)
    
    return np.array(srcImage1_matchedKPs),np.array(srcImage2_matchedKPs)



# Input: expects Nx3 matrix of points
# Returns R,t
# R = 3x3 rotation matrix
# t = 3x1 column vector

def rigid_transform_3D(A, B):
    assert len(A) == len(B)

    N = A.shape[0]  # total points
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)

    # centre the points
    AA = A - np.tile(centroid_A, (N, 1))
    BB = B - np.tile(centroid_B, (N, 1))

    H = np.matmul(np.transpose(AA),BB)
    U, S, Vt = np.linalg.svd(H)
    R = np.matmul(Vt.T, U.T)

    # special reflection case
    if np.linalg.det(R) < 0:
        print("Reflection detected")
        Vt[2, :] *= -1
        R = np.matmul(Vt.T,U.T)

    t = -np.matmul(R, centroid_A) + centroid_B
    # err = B - np.matmul(A,R.T) - t.reshape([1, 3])
    return R, t

def gaug(src,br,ctr):

    image = Image.fromarray(cv2.cvtColor(src,cv2.COLOR_GRAY2RGB))
    enh_bri = ImageEnhance.Brightness(image)
    brightness = br
    image_brightened = enh_bri.enhance(brightness)
    enh_col = ImageEnhance.Color(image_brightened)
    color = 1
    image_colored = enh_col.enhance(color)
    enh_con = ImageEnhance.Contrast(image_colored)
    contrast = ctr
    image_contrasted = enh_con.enhance(contrast)
    dst=np.asarray(image_contrasted)
    #out=cv2.pyrMeanShiftFiltering(dst,10,10)
    out=cv2.medianBlur(dst, 5)
    # out=cv2.GaussianBlur(dst, (11,11), 0)
    #out = cv2.Canny(out, 100, 255)
    # ret, out = cv2.threshold(out,150, 255, 0)
    #out=cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    return out
def tran16to8(image_16bit):
    p = np.percentile(image_16bit, 99.99)
    min_16bit = 0
    vmin=0
    vmax=2000
    # if (p>vmin) and (p<vmax):
    #     max_16bit = p
    # elif p>vmax:
    #     max_16bit = vmax
    # elif p<vmin:
    #     max_16bit = vmin
    max_16bit=vmax
    scaled_image = np.clip(image_16bit, min_16bit, max_16bit)  # 将超过范围的值截断到范围内
    image_8bit = np.array(np.rint(255 * ((scaled_image - min_16bit) / (max_16bit - min_16bit))), dtype=np.uint8)
    # image_8bit = multiScaleSharpen_v1(image_8bit,9)
    return image_8bit
def del_file(path):
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            del_file(c_path)
        else:
            os.remove(c_path)
def pmake(path):
    if os.path.exists(path):
        pass
    else:
        os.makedirs(path)
def mulfra_mulr_1r_regist(framenum,rnum,inbase,outbase,Hmode=0):
    superworkdir = './super_workdir/'

    if os.path.exists(superworkdir):
        pass
    else:
        os.makedirs(superworkdir)
    w_pad = 0
    H0 = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]]).astype(float)
    # deformed_image = warp(torch.tensor(field),torch.tensor(imgt2))
    br = 1
    ctr = 10
    for idx in range(framenum[0], framenum[1]):  # frame数
        Hlist = []
        Ho = None
        for ir in range(0, rnum):  # 轮次数
            if ir == 0:
                imgr1c1 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch1.png', -1)  # 以通道1第一张图为基准
                h = imgr1c1.shape[0]
                w = imgr1c1.shape[1]
                # imgr1c1 = tran16to8(imgr1c1)
                # cv2.imwrite(f'./regidata/V_{imgname}F{idx}R{ir+1}.png',imgr1c1)
                imgr1c1a = gaug(imgr1c1, br, ctr)
                cv2.imwrite(f'{superworkdir}1.png', imgr1c1a)  # 存储到superpoint工作区
                # r1c1 =gaug(imgr1c1,1,2)
                r1c1 = imgr1c1
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch1.png', r1c1)

                imgr1c2 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch2.png', -1)
                r1c2 = imgr1c2
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch2.png', r1c2)

                imgr1c3 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch3.png', -1)
                r1c3 = imgr1c3
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch3.png', r1c3)

                imgr1c4 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch4.png', -1)
                r1c4 = imgr1c4
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch4.png', r1c4)
                Hf = np.array(H0, dtype=np.float32)
                Ho = np.round(Hf.reshape(1, 9), decimals=6)
                Hlist.append(Ho)
            else:
                imgrxc1 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch1.png', -1)  # 以通道1第一张图为基准
                # imgrxc1 = tran16to8(imgrxc1)
                # cv2.imwrite(f'./regidata/V_{imgname}F{idx}R{ir+1}Ch1.png',imgrxc1)
                imgrxc1a = gaug(imgrxc1, br, ctr)
                cv2.imwrite(f'{superworkdir}2.png', imgrxc1a)  # 存储到superpoint工作区
                print(f"目前正在处理frame{idx},R{ir + 1}:")
                # 开始配准，register(浮动图像，参考图像，上面设置的变量)
                # im3, field = pyelastix.register(imgrxc1a, imgr1c1a, params)
                im1, im2, p0, p1 = superfeature(superworkdir, h, w, imgr1c1a, imgrxc1a)
                # #####下面是计算单应性矩阵#####################
                if Hmode == 0:
                    ransacReprojThreshold = 10
                    H, status = cv2.findHomography(p0, p1, cv2.RHO, ransacReprojThreshold)  # 基准和输入
                    Hf = np.array(H, dtype=np.float32)
                    Hf[0, 2] = -Hf[0, 2]
                    Hf[1, 2] = -Hf[1, 2]
                    Ho = np.round(Hf.reshape(1, 9), decimals=8)
                elif Hmode == 1:
                    ######## 构建平移矩阵的方法########
                    mean_tx = np.mean(p1[:, 0] - p0[:, 0])
                    mean_ty = np.mean(p1[:, 1] - p0[:, 1])
                    # 构建只包含平移信息的H矩阵
                    H = np.array([[1, 0, mean_tx],
                                  [0, 1, mean_ty],
                                  [0, 0, 1]], dtype=np.float32)
                    Hf = np.array(H, dtype=np.float32)
                    Ho = np.round(Hf.reshape(1, 9), decimals=6)
                Hlist.append(Ho)
                ##########使用H矩阵###############
                # rxc1 = cv2.warpAffine(imgrxc1, T,(r1c1.shape[1], r1c1.shape[0])) # 配准通道匹配结果
                rxc1 = siftPointAlignment(imgrxc1, H, w_pad)
                # rxc1 = gaug(siftPointAlignment(imgrxc1, H, w_pad),1,2)
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch1.png', rxc1)

                imgrxc2 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch2.png', -1)
                rxc2 = siftPointAlignment(imgrxc2, H, w_pad)
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch2.png', rxc2)

                imgrxc3 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch3.png', -1)
                rxc3 = siftPointAlignment(imgrxc3, H, w_pad)
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch3.png', rxc3)

                imgrxc4 = cv2.imread(f'{inbase}F{idx}R{ir + 1}Ch4.png', -1)
                rxc4 = siftPointAlignment(imgrxc4, H, w_pad)
                cv2.imwrite(f'{outbase}img/F{idx}R{ir + 1}Ch4.png', rxc4)
        csv_file_path = f"{outbase}csv/F{idx}.txt"
        with open(csv_file_path, mode='w+', newline='') as file:
            writer = csv.writer(file)
            for i in range(len(Hlist)):
                writer.writerow(Hlist[i][0])


def stitchWithFeature(inpath,outpath):
    Stitcher.featureMethod = "super"             # "sift","surf" or "orb","super"
    Stitcher.isColorMode = False                 # True:color, False: gray
    Stitcher.isGPUAvailable = False
    # Stitcher.isEnhance = True
    # Stitcher.isClahe = True
    Stitcher.superthresh=0.4                     #superpoint match thresh 359row,47row&,327row
    Stitcher.searchRatio = 0.75                 # 0.75 is common value for matches
    Stitcher.offsetCaculate = "mode"            # "mode" or "ransac"
    Stitcher.offsetEvaluate = 3                 # 3 menas nums of matches for mode, 3.0 menas  of matches for ransac
    Stitcher.roiRatio = 0.2                     # roi length for stitching in first direction
    Stitcher.fuseMethod = "fadeInAndFadeOut"    # "notFuse","average","maximum","minimum","fadeInAndFadeOut","trigonometric", "multiBandBlending"
    Stitcher.direction = 2;  Stitcher.directIncre = -1;#拼接方向设定，direction：1从上到下，2从左到右，3从下到上，4从右到左
    Stitcher.ishandle = True                    #是否手动拼接
    stitcher = Stitcher()

    filename = natsorted(os.listdir(inpath))
    Rr=0
    Rch=0
    for r in filename:
        chfile = natsorted(os.listdir(inpath+"/" + r))
        for ch in chfile:
            if ch[-1] == '1'and r[-1]=='1':
                stitcher.imageSetStitchWithMutiple(f'{inpath}{r}/{ch}', f'{outpath}{r}/{ch}', 1,
                                                                        stitcher.calculateOffsetForFeatureSearchIncre,
                                                                        startNum=1, fileExtension="png",
                                                                        outputfileExtension="png",r=r,ch=ch,outpath=outpath)
                Rr=r
                Rch=ch
        for ch in chfile:
            stnum=0
            endnum=0
            dpath=[]
            for filename in os.listdir(f'{outpath}{Rr}/{Rch}'):##检查dxdy文件数量
                # 检查文件名是否包含'dxdy'并且以'.txt'结尾
                if 'dxdy' in filename and filename.endswith('.txt'):
                    # 拼接完整文件路径
                    dpath.append(os.path.join(f'{outpath}{Rr}/{Rch}', filename))
            for lix in range(0,len(dpath)):
                offsetlist = []
                with open(dpath[lix], 'r') as file:
                    for line in file:
                        # 去除每行末尾的换行符，并添加到列表
                        parts = line.strip().split()
                        # 将分割后的部分转换为整数
                        int_parts = [int(part) for part in parts]
                        # 添加整数列表到 offsetlist
                        offsetlist.append(int_parts)
                # offsetlist=[int(item) for item in offsetlist]
                endnum= int(re.search(r'dxdy(\d+)', dpath[lix]).group(1))
                pmake(f'{outpath}{r}/{ch}')
                fileAddress = f'{inpath}{r}/{ch}' + "\\1" + "\\"
                fileList = natsorted(glob.glob(fileAddress + "*.png"))
                selected_files = fileList[stnum:endnum]
                stitimage, _ = stitcher.getStitchByOffset(selected_files, offsetlist)
                cv2.imwrite(f'{outpath}{r}/{ch}' + f"\\stitching_result{stnum+1}-{endnum}" + ".png", stitimage)
                os.remove(f'{outpath}{r}/{ch}' + f"\\stitching_result_1" + ".png")
                stnum+=endnum