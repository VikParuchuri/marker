# An Aggregated Multicolumn Dilated Convolution Network For Perspective-Free Counting

Diptodip Deb Georgia Institute of Technology Jonathan Ventura University of Colorado Colorado Springs diptodipdeb@gatech.edu

## Abstract

We propose the use of dilated filters to construct an aggregation module in a multicolumn convolutional neural network for perspective-free counting. Counting is a common problem in computer vision (e.g. traffic on the street or pedestrians in a crowd). Modern approaches to the counting problem involve the production of a density map via regression whose integral is equal to the number of objects in the image. However, objects in the image can occur at different scales (e.g. due to perspective effects) which can make it difficult for a learning agent to learn the proper density map. While the use of multiple columns to extract multiscale information from images has been shown before, our approach aggregates the multiscale information gathered by the multicolumn convolutional neural network to improve performance. Our experiments show that our proposed network outperforms the state-of-the-art on many benchmark datasets, and also that using our aggregation module in combination with a higher number of columns is beneficial for multiscale counting.

## 1. Introduction

Learning to count the number of objects in an image is a deceptively difficult problem with many interesting applications, such as surveillance [20], traffic monitoring [14] and medical image analysis [22]. In many of these application areas, the objects to be counted vary widely in appearance, size and shape, and labeled training data is typically sparse. These factors pose a significant computer vision and machine learning challenge.

Lempitsky et al. [15] showed that it is possible to learn to count without learning to explicitly detect and localize individual objects. Instead, they propose learning to predict a density map whose integral over the image equals the number of objects in the image. This approach has been adopted by many later works (Cf. [18,28]).

However, in many counting problems, such as those jventura@uccs.edu counting cells in a microscope image, pedestrians in a crowd, or vehicles in a traffic jam, regressors trained on a single image scale are not reliable [18]. This is due to a variety of challenges including overlap of objects and perspective effects which cause significant variance in object shape, size and appearance.

The most successful recent approaches address this issue by explicitly incorporating multi-scale information in the network [18,28]. These approaches either combine multiple networks which take input patches of different sizes [18] or combine multiple filtering paths ("columns") which have different size filters [28].

Following on the intuition that multiscale integration is key to achieving good counting performance, we propose to incorporate dilated filters [25] into a multicolumn convolutional neural network design [28]. Dilated filters exponentially increase the network's receptive field without an exponential increase in parameters, allowing for efficient use of multiscale information. Convolutional neural networks with dilated filters have proven to provide competitive performance in image segmentation where multiscale analysis is also critical [25, 26]. By incorporating dilated filters into the multicolumn network design, we greatly increase the ability of the network to selectively aggregate multiscale information, without the need for explicit perspective maps during training and testing. We propose the "aggregated multicolumn dilated convolution network" or AMDCN which uses dilations to aggregate multiscale information. Our extensive experimental evaluation shows that this proposed network outperforms previous methods on many benchmark datasets.

## 2. Related Work

Counting using a supervised regressor to formulate a density map was first shown by [15]. In this paper, Lempitsky et al. show that the minimal annotation of a single dot blurred by a Gaussian kernel produces a sufficient density map to train a network to count. All of the counting methods that we examine as well as the method we use in our paper follow this method of producing a density map via regression. This is particularly advantageous because a sufficiently accurate regressor can also locate the objects in the image via this method. However, the Lempitsky paper ignores the issue of perspective scaling and other scaling issues. The work of [27] introduces CNNs (convolutional neural networks) for the purposes of crowd counting, but performs regression on similarly scaled image patches.

These issues are addressed by the work of [18]. Rubio et al. show that a fully convolutional neural network can be used to produce a supervised regressor that produces density maps as in [15]. They further demonstrate a method dubbed HydraCNN which essentially combines multiple convolutional networks that take in differently scaled image patches in order to incorporate multiscale, global information from the image. The premise of this method is that a single regressor will fail to accurately represent the difference in values of the features of an image caused by perspective shifts (scaling effects) [18].

However, the architectures of both [18] and [27] are not fully convolutional due to requiring multiple image patches and, as discussed in [25], the experiments of [11, 17] and [9, 12, 16] leave it unclear as to whether rescaling patches of the image is truly necessary in order to solve dense prediction problems via convolutional neural networks. Moreover, these approaches seem to saturate in performance at three columns, which means the network is extracting information from fewer scales. The work of [25] proposes the use of dilated convolutions as a simpler alternative that does not require sampling of rescaled image patches to provide global, scale-aware information to the network. A fully convolutional approach to multiscale counting has been proposed by [28], in which a multicolumn convolutional network gathers features of different scales by using convolutions of increasing kernel sizes from column to column instead of scaling image patches. Further, DeepLab has used dilated convolutions in multiple columns to extract scale information for segmentation [8]. We build on these approaches with our aggregator module as described in Section 3.1, which should allow for extracting information from more scales.

It should be noted that other methods of counting exist, including training a network to recognize deep object features via only providing the counts of the objects of interest in an image [21] and using CNNs (convolutional neural networks) along with boosting in order to improve the results

## ![Im103.Png](Temp Files/Im103.Png)

of regression for production of density maps [24]. In the same spirit, [4] combines deep and shallow convolutions within the same network, providing accurate counting of dense objects (e.g. the UCF50 crowd dataset).

In this paper, however, we aim to apply the dilated convolution method of [25], which has shown to be able to incorporate multiscale perspective information without using multiple inputs or a complicated network architecture, as well as the multicolumn approach of [8, 28] to aggregate multiscale information for the counting problem.

## 3. Method 3.1. Dilated Convolutions For Multicolumn Networks

We propose the use of dilated convolutions as an attractive alternative to the architecture of the HydraCNN [18], which seems to saturate in performance at 3 or more columns.

We refer to our proposed network as the aggregated multicolumn dilated convolution network1, henceforth shortened as the AMDCN. The architecture of the AMDCN is inspired by the multicolumn counting network of [28]. Extracting features from multiple scales is a good idea when attempting to perform perspective-free counting and increasing the convolution kernel size across columns is an efficient method of doing so. However, the number of parameters increases exponentially as larger kernels are used in these columns to extract features at larger scales. Therefore, we propose using dilated convolutions rather than larger kernels.

Dilated convolutions, as discussed in [25], allow for the exponential increase of the receptive field with a linear increase in the number of parameters with respect to each hidden layer.

In a traditional 2D convolution, we define a real valued function F : Z2 → R, an input Ωr = [−*r, r*]2 ∈ Z2, and a filter function k : Ωr → R. In this case, a convolution operation as defined in [25] is given by

$$(F*k)(p)=\sum_{\bf s+t=p}F({\bf s})k({\bf t}). \tag{1}$$
A dilated convolution is essentially a generalization of the traditional 2D convolution that allows the operation to skip some inputs. This enables an increase in the size of the filter (i.e. the size of the receptive field) without losing resolution. Formally, we define from [25] the dilated convolution as

$$(F*_{l}k)({\bf p})=\sum_{l}F({\bf s})k({\bf t}) \tag{2}$$
where l is the index of the current layer of the convolution.

Using dilations to construct the aggregator in combination with the multicolumn idea will allow for the construction of a network with more than just 3 or 4 columns as in [28] and [8], because the aggregator should prevent the saturation of performance with increasing numbers of columns. Therefore the network will be able to extract useful features from more scales. We take advantage of dilations within the columns as well to provide large receptive fields with fewer parameters.

Looking at more scales should allow for more accurate regression of the density map. However, because not all scales will be relevant, we extend the network beyond a simple 1 × 1 convolution after the merged columns. Instead, we construct a second part of the network, the aggregator, which sets our method apart from [28], [8], and other multicolumn networks. This aggregator is another series of dilated convolutions that should appropriately consolidate the multiscale information collected by the columns. This is a capability of dilated convolutions observed by [25]. While papers such as [28] and [8] have shown that multiple columns and dilated columns are useful in extracting multiscale information, we argue in this paper that the simple aggregator module built using dilated convolutions is able to effectively make use multiscale information from multiple columns. We show compelling evidence for these claims in Section 4.5.

The network as shown in Figure 1 contains 5 columns.

Note that dilations allow us to use more columns for counting than [28] or [8]. Each column looks at a larger scale than the previous (the exact dilations can also be seen in Figure 1). There are 32 feature maps for each convolution, and all inputs are zero padded prior to each convolution in order to maintain the same data shape from input to output. That is, an image input to this network will result in a density map of the same dimensions. All activations in the specified network are ReLUs. Our input pixel values are floating point 32 bit values from 0 to 1. We center our inputs at 0 by subtracting the per channel mean from each channel. When