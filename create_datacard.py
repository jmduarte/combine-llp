from __future__ import print_function, division
import os
import rhalphalib as rl
import numpy as np
import pickle
import uproot
rl.util.install_roofit_helpers()
rl.ParametericSample.PreferRooParametricHist = False


def get_hist(inputfile, name, obs):
    upfile = uproot.open(inputfile)
    hist_values = upfile[name].values()
    hist_edges = upfile[name].axis().edges()
    hist_uncs = upfile[name].variances()
    if obs.binning != hist_edges:
        # rebin (assumes new bins are a subset of existing bins)
        edge_mask = np.in1d(hist_edges, obs.binning)
        hist_mask = np.logical_and(edge_mask[0:-1], edge_mask[1:])
        hist_values = hist_values[hist_mask]
        hist_edges = hist_edges[edge_mask]
        hist_uncs = hist_uncs[hist_mask]
    return (hist_values, hist_edges, obs.name, hist_uncs)


def create_datacard(inputfile, carddir, nbins, nMCTF, nDataTF, passBinName, failBinName='fail', add_unblinded=False, include_ac=False):

    regionPairs = [('pass'+passBinName, failBinName)]  # pass, fail region pairs
    if add_unblinded:
        regionPairs += [('SR'+passBinName, 'fit'+failBinName)]

    regions = [item for t in regionPairs for item in t]  # all regions

    ttbarBin1MCstats = rl.NuisanceParameter('ttbarBin1_yieldMCStats', 'lnN')
    lumi = rl.NuisanceParameter('CMS_lumi', 'lnN')
    trigSF = rl.NuisanceParameter('triggerEffSF_correlated', 'lnN')
    PNetHbbScaleFactorssyst = rl.NuisanceParameter('PNetHbbScaleFactors_correlated', 'lnN')

    msdbins = np.linspace(50, nbins*10.0+50.0, nbins+1)
    msd = rl.Observable('msd', msdbins)
    msdpts = msdbins[:-1] + 0.5 * np.diff(msdbins)
    msdscaled = (msdpts - 50.)/(10.0*nbins)

    # Build qcd MC pass+fail model and fit to polynomial
    qcdmodel = rl.Model('qcdmodel')
    qcdpass, qcdfitfail = 0., 0.
    passCh = rl.Channel('passqcdmodel')
    fitfailCh = rl.Channel('fitfailqcdmodel')
    qcdmodel.addChannel(fitfailCh)
    qcdmodel.addChannel(passCh)

    # pseudodata MC template
    passTempl = get_hist(inputfile, 'histJet2MassBlind_'+passBinName+'_QCD', obs=msd)
    fitfailTempl = get_hist(inputfile, 'histJet2Massfit_fail_QCD', obs=msd)

    passCh.setObservation(passTempl[:-1])
    fitfailCh.setObservation(fitfailTempl[:-1])
    qcdpass = passCh.getObservation().sum()
    qcdfitfail = fitfailCh.getObservation().sum()

    qcdeffpass = qcdpass / qcdfitfail

    # transfer factor
    tf_dataResidual = rl.BernsteinPoly("tf_dataResidual_"+passBinName, (nDataTF,), ['msd'], limits=(-20, 20))
    tf_dataResidual_params = tf_dataResidual(msdscaled)
    tf_params_pass = qcdeffpass * tf_dataResidual_params

    # qcd params
    qcdparams = np.array([rl.IndependentParameter('qcdparam_msdbin%d' % i, 0) for i in range(msd.nbins)])

    # build actual fit model now
    model = rl.Model("HHModel")
    for region in regions:
        print('INFO: starting region: %s' % region)
        ch = rl.Channel(region)
        model.addChannel(ch)

        if region == 'pass'+passBinName:
            catn = 'Blind_'+passBinName
        elif region == 'SR'+passBinName:
            catn = '_'+passBinName
        elif region == 'fit'+failBinName:
            catn = 'fit_'+failBinName
        else:
            catn = 'Blind_'+failBinName

        templates = {
            'TTJets': get_hist(inputfile, 'histJet2Mass'+catn+'_TTJets', obs=msd),
            'ggHH_kl_1_kt_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_ggHH_kl_1_kt_1_boost4b', obs=msd),
            'qqHH_CV_1_C2V_1_kl_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1_C2V_1_kl_1_boost4b', obs=msd),
            'VH': get_hist(inputfile, 'histJet2Mass'+catn+'_VH', obs=msd),
            'ttH': get_hist(inputfile, 'histJet2Mass'+catn+'_ttH', obs=msd),
            'others': get_hist(inputfile, 'histJet2Mass'+catn+'_others', obs=msd),
            'QCD': get_hist(inputfile, 'histJet2Mass'+catn+'_QCD', obs=msd),
            'Data': get_hist(inputfile, 'histJet2Mass'+catn+'_Data', obs=msd),
        }

        if include_ac:
            templates.update({
                'ggHH_kl_2p45_kt_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_ggHH_kl_2p45_kt_1_boost4b', obs=msd),
                'ggHH_kl_5_kt_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_ggHH_kl_5_kt_1_boost4b', obs=msd),
                'qqHH_CV_1_C2V_0_kl_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1_C2V_0_kl_1_boost4b', obs=msd),
                'qqHH_CV_1p5_C2V_1_kl_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1p5_C2V_1_kl_1_boost4b', obs=msd),
                'qqHH_CV_1_C2V_1_kl_2_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1_C2V_1_kl_2_boost4b', obs=msd),
                'qqHH_CV_1_C2V_2_kl_1_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1_C2V_2_kl_1_boost4b', obs=msd),
                'qqHH_CV_1_C2V_1_kl_0_boost4b': get_hist(inputfile, 'histJet2Mass'+catn+'_qqHH_CV_1_C2V_1_kl_0_boost4b', obs=msd)
            })

        # dictionary of systematics -> name in cards
        systs = {
            'ttbarBin1Jet2PNetCut': 'ttbarBin1Jet2PNetCut',
            'FSRPartonShower': 'FSRPartonShower',
            'ISRPartonShower': 'ISRPartonShower',
            'ggHHPDFacc': 'ggHHPDFacc',
            'ggHHQCDacc': 'ggHHQCDacc',
            'pileupWeight': 'CMS_pileup',
            'JER': 'CMS_JER',
            'JES': 'CMS_JES',
            'JMS': 'CMS_JMS',
            'JMR': 'CMS_JMR',
            'ttJetsCorr': 'ttJetsCorr',
            'BDTShape': 'ttJetsBDTShape',
            'PNetShape': 'ttJetsPNetShape',
            'PNetHbbScaleFactors': 'PNetHbbScaleFactors_uncorrelated',
            'triggerEffSF': 'triggerEffSF_uncorrelated'
        }

        syst_param_array = []
        for syst in systs:
            syst_param_array.append(rl.NuisanceParameter(systs[syst], 'shape'))

        sNames = [proc for proc in templates.keys() if proc not in ['QCD', 'Data']]
        for sName in sNames:
            print('INFO: get templates for: %s' % sName)
            # get templates
            templ = templates[sName]
            stype = rl.Sample.SIGNAL if 'HH' in sName else rl.Sample.BACKGROUND
            sample = rl.TemplateSample(ch.name + '_' + sName, stype, templ)

            sample.setParamEffect(lumi, 1.016)
            sample.setParamEffect(trigSF, 1.04)

            if sName == "TTJets" and "Bin1" in region:
                if region == "passBin1":
                    sample.setParamEffect(ttbarBin1MCstats, 1.215)
                elif region == "SRBin1":
                    sample.setParamEffect(ttbarBin1MCstats, 1.187)

            if ("VH" in sName) or ("ttH" in sName):
                sample.setParamEffect(PNetHbbScaleFactorssyst, 1.04)
            elif "HH" in sName:
                sample.setParamEffect(PNetHbbScaleFactorssyst, 1.0816)

            # set mc stat uncs
            print('INFO: setting autoMCStats for %s' % sName)
            sample.autoMCStats()

            # shape systematics
            valuesNominal = templ[0]

            for isyst, syst in enumerate(systs):
                print('INFO: setting shape effect %s for %s' % (syst, sName))
                valuesUp = get_hist(inputfile, 'histJet2Mass'+catn+'_%s_%sUp' % (sName, syst), obs=msd)[0]
                valuesDown = get_hist(inputfile, 'histJet2Mass'+catn+'_%s_%sDown' % (sName, syst), obs=msd)[0]
                effectUp = np.ones_like(valuesNominal)
                effectDown = np.ones_like(valuesNominal)
                for i in range(len(valuesNominal)):
                    if valuesNominal[i] > 0.:
                        effectUp[i] = valuesUp[i]/valuesNominal[i]
                        effectDown[i] = valuesDown[i]/valuesNominal[i]
                sample.setParamEffect(syst_param_array[isyst], effectUp, effectDown)
            ch.addSample(sample)

        # data observed
        yields = templates['Data'][0]
        data_obs = (yields, msd.binning, msd.name)
        ch.setObservation(data_obs)

    for passChName, failChName in regionPairs:
        print('INFO: setting transfer factor for pass region %s, fail region %s' % (passChName, failChName))
        failCh = model[failChName]
        passCh = model[passChName]

        # sideband fail
        initial_qcd = failCh.getObservation().astype(float)  # was integer, and numpy complained about subtracting float from it
        for sample in failCh:
            initial_qcd -= sample.getExpectation(nominal=True)
        if np.any(initial_qcd < 0.):
            raise ValueError("initial_qcd negative for some bins..", initial_qcd)
        sigmascale = 10  # to scale the deviation from initial
        scaledparams = initial_qcd * (1 + sigmascale/np.maximum(1., np.sqrt(initial_qcd)))**qcdparams

        # add samples
        fail_qcd = rl.ParametericSample(failChName+'_qcd', rl.Sample.BACKGROUND, msd, scaledparams)
        failCh.addSample(fail_qcd)

        pass_qcd = rl.TransferFactorSample(passChName+'_qcd', rl.Sample.BACKGROUND, tf_params_pass, fail_qcd)
        passCh.addSample(pass_qcd)

    with open(os.path.join(str(carddir), 'HHModel.pkl'), "wb") as fout:
        pickle.dump(model, fout)

    print('INFO: rendering combine model')
    model.renderCombine(os.path.join(str(carddir), 'HHModel'))


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--inputfile', default='HHTo4BPlots_Run2_BDTv8p2_0311_syst_Trigv0.root', type=str, dest='inputfile', help='input ROOT file')
    parser.add_argument('--carddir', default='cards', type=str, dest='carddir', help='output card directory')
    parser.add_argument('--nbins', default=17, type=int, dest='nbins', help='number of bins')
    parser.add_argument('--nMCTF', default=0, type=int, dest='nMCTF', help='order of polynomial for TF from MC')
    parser.add_argument('--nDataTF', default=2, type=int, dest='nDataTF', help='order of polynomial for TF from Data')
    parser.add_argument('--passBinName', default='Bin1', type=str, choices=['Bin1', 'Bin2', 'Bin3'], help='pass bin name')

    args = parser.parse_args()
    if not os.path.exists(args.carddir):
        os.mkdir(args.carddir)
    create_datacard(args.inputfile, args.carddir, args.nbins, args.nMCTF, args.nDataTF, args.passBinName, "fail")
